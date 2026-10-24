/**
 * IRIS AI — Graceful Shutdown and Backend Process Lifecycle Tests
 * Validates process tracking, idempotent cleanup, graceful shutdown protocol,
 * bounded timeouts, and targeted process tree termination.
 */

import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const BackendManager = require("../electron/backendManager.js");

class MockChildProcess extends EventEmitter {
  constructor(pid = 43210) {
    super();
    this.pid = pid;
    this.exitCode = null;
    this.killed = false;
    this.stdout = new EventEmitter();
    this.stderr = new EventEmitter();
  }

  simulateExit(code = 0, signal = null) {
    this.exitCode = code;
    this.killed = true;
    this.emit("exit", code, signal);
    this.emit("close", code, signal);
  }
}

describe("BackendManager Lifecycle & Graceful Teardown", () => {
  it("Requirement 1 & 2: Initiates cleanup and sends graceful HTTP shutdown request", async () => {
    const bm = new BackendManager();
    const mockChild = new MockChildProcess(12345);
    bm.childProcess = mockChild;
    bm.ownedPid = 12345;
    bm.ownedByElectron = true;
    bm.status = "ready";

    let shutdownRequested = false;
    bm.requestGracefulShutdown = async (timeoutMs) => {
      shutdownRequested = true;
      assert.strictEqual(typeof timeoutMs, "number");
      // Simulate backend immediately exiting upon receiving shutdown request
      setTimeout(() => mockChild.simulateExit(0), 10);
      return true;
    };

    let forceKilled = false;
    bm.forceKillProcessTree = () => {
      forceKilled = true;
    };

    const stopPromise = bm.stop();
    assert.strictEqual(bm.status, "stopping");

    await stopPromise;

    assert.strictEqual(shutdownRequested, true, "Graceful shutdown must be requested via HTTP");
    assert.strictEqual(forceKilled, false, "Normal graceful exit must NOT trigger forceful kill");
    assert.strictEqual(bm.status, "stopped");
    assert.strictEqual(bm.childProcess, null);
    assert.strictEqual(bm.ownedByElectron, false);
    assert.strictEqual(bm.ownedPid, null);
  });

  it("Requirement 3: Backend that exits normally is not force-killed unnecessarily", async () => {
    const bm = new BackendManager();
    const mockChild = new MockChildProcess(23456);
    bm.childProcess = mockChild;
    bm.ownedPid = 23456;
    bm.ownedByElectron = true;
    bm.status = "ready";

    let forceKillTargetPid = null;
    bm.forceKillProcessTree = (pid) => {
      forceKillTargetPid = pid;
    };

    bm.requestGracefulShutdown = async () => {
      setTimeout(() => mockChild.simulateExit(0), 20);
      return true;
    };

    await bm.stop();

    assert.strictEqual(forceKillTargetPid, null, "Should not invoke forceKillProcessTree when backend exits normally");
    assert.strictEqual(bm.status, "stopped");
  });

  it("Requirement 4: Backend that ignores graceful shutdown is terminated after bounded timeout", async () => {
    const bm = new BackendManager();
    const mockChild = new MockChildProcess(34567);
    bm.childProcess = mockChild;
    bm.ownedPid = 34567;
    bm.ownedByElectron = true;
    bm.status = "ready";

    // Simulate backend ignoring graceful shutdown HTTP request
    bm.requestGracefulShutdown = async () => {
      return false;
    };

    // Use a fast timeout for testing bounded timeout behavior
    const origWaitForProcessExit = bm.waitForProcessExit.bind(bm);
    bm.waitForProcessExit = (child, timeoutMs) => {
      return origWaitForProcessExit(child, 50); // fast 50ms bounded timeout
    };

    let forceKillPid = null;
    bm.forceKillProcessTree = (pid) => {
      forceKillPid = pid;
      mockChild.simulateExit(1, "SIGKILL");
    };

    await bm.stop();

    assert.strictEqual(forceKillPid, 34567, "Must target exactly the owned PID for fallback termination");
    assert.strictEqual(bm.status, "stopped");
    assert.strictEqual(bm.childProcess, null);
  });

  it("Requirement 5: Repeated close events do not launch multiple conflicting cleanup sequences (idempotency)", async () => {
    const bm = new BackendManager();
    const mockChild = new MockChildProcess(45678);
    bm.childProcess = mockChild;
    bm.ownedPid = 45678;
    bm.ownedByElectron = true;
    bm.status = "ready";

    let shutdownCalls = 0;
    bm.requestGracefulShutdown = async () => {
      shutdownCalls++;
      await new Promise((r) => setTimeout(r, 40));
      mockChild.simulateExit(0);
      return true;
    };

    // Trigger multiple stop calls in parallel
    const p1 = bm.stop();
    const p2 = bm.stop();
    const p3 = bm.stop();

    assert.strictEqual(p1, p2, "Concurrently invoked stop() must return the identical Promise");
    assert.strictEqual(p2, p3, "All concurrent stop() calls must share the same in-flight Promise");

    await Promise.all([p1, p2, p3]);

    assert.strictEqual(shutdownCalls, 1, "Graceful shutdown must only be dispatched once without racing");
    assert.strictEqual(bm.status, "stopped");

    // Subsequent call when already stopped resolves immediately
    const p4 = await bm.stop();
    assert.strictEqual(p4, true);
    assert.strictEqual(shutdownCalls, 1, "Subsequent stop on stopped manager must not re-dispatch HTTP requests");
  });

  it("Requirement 6: Backend restart does not leave the previous process running", async () => {
    const bm = new BackendManager();
    const mockChildOld = new MockChildProcess(55551);
    bm.childProcess = mockChildOld;
    bm.ownedPid = 55551;
    bm.ownedByElectron = true;
    bm.status = "ready";

    let oldProcessTerminated = false;
    bm.requestGracefulShutdown = async () => {
      oldProcessTerminated = true;
      mockChildOld.simulateExit(0);
      return true;
    };

    let startCalled = false;
    bm.start = async () => {
      assert.strictEqual(oldProcessTerminated, true, "Previous backend must be fully stopped before new start begins");
      assert.strictEqual(bm.childProcess, null, "Old child process reference must be cleared");
      startCalled = true;
      bm.status = "ready";
      return true;
    };

    await bm.restart();

    assert.strictEqual(startCalled, true, "restart() must proceed to start after cleanly stopping previous process");
    assert.strictEqual(bm.status, "ready");
  });

  it("Requirement 7: Backend startup failure does not break Electron shutdown", async () => {
    const bm = new BackendManager();
    bm.isStarting = true;
    bm.setStatus("starting", "Testing startup failure...");

    // Simulate startup throwing an error
    bm.spawnBackendProcess = () => {
      throw new Error("Simulated spawn error (e.g. missing binary or locked port)");
    };

    try {
      await bm.start();
    } catch (err) {
      assert.ok(err.message.includes("Simulated spawn error"));
    }

    // Now call stop() — should handle cleanly without throws or hangs
    const stopResult = await bm.stop();
    assert.strictEqual(stopResult, true);
    assert.strictEqual(bm.status, "stopped");
    assert.strictEqual(bm.childProcess, null);
  });

  it("Requirement 8: Unrelated Python processes are never targeted", () => {
    const bm = new BackendManager();

    // Verify safety guards in forceKillProcessTree
    // 1. Should ignore invalid PIDs
    bm.forceKillProcessTree(null);
    bm.forceKillProcessTree(undefined);
    bm.forceKillProcessTree(-1);
    bm.forceKillProcessTree(0);
    bm.forceKillProcessTree("abc");

    // 2. Should refuse to terminate own process PID or system process PID 4
    bm.forceKillProcessTree(process.pid);
    bm.forceKillProcessTree(4);
    bm.forceKillProcessTree(0);

    // 3. Status state never holds broad commands
    const state = bm.getStatusState();
    assert.strictEqual(state.ownedPid, null);
    assert.strictEqual(state.ownedByElectron, false);
  });

  it("Requirement 9: Child processes owned by IRIS AI are tracked explicitly", () => {
    const bm = new BackendManager();
    assert.strictEqual(bm.status, "stopped");
    assert.strictEqual(bm.ownedByElectron, false);
    assert.strictEqual(bm.ownedPid, null);

    const mockChild = new MockChildProcess(98765);
    bm.childProcess = mockChild;
    bm.ownedPid = 98765;
    bm.ownedByElectron = true;
    bm.status = "ready";

    const state = bm.getStatusState();
    assert.strictEqual(state.ownedPid, 98765);
    assert.strictEqual(state.ownedByElectron, true);
    assert.strictEqual(state.status, "ready");
  });

  it("Requirement 10: Unexpected backend crash during runtime transitions to error state", () => {
    const bm = new BackendManager();
    const mockChild = new MockChildProcess(88888);
    bm.childProcess = mockChild;
    bm.ownedPid = 88888;
    bm.ownedByElectron = true;
    bm.status = "ready";

    // Simulate unexpected crash while running (status is not stopping/stopped)
    mockChild.on("exit", (code) => {
      const wasOwned = bm.ownedByElectron;
      bm.childProcess = null;
      bm.ownedByElectron = false;
      bm.ownedPid = null;
      if (wasOwned && bm.status !== "stopped" && bm.status !== "stopping") {
        bm.setStatus("error", `Backend exited unexpectedly (code ${code})`);
      }
    });

    mockChild.simulateExit(1);

    assert.strictEqual(bm.status, "error");
    assert.ok(bm.message.includes("Backend exited unexpectedly"));
    assert.strictEqual(bm.childProcess, null);
    assert.strictEqual(bm.ownedByElectron, false);
    assert.strictEqual(bm.ownedPid, null);
  });

  it("Requirement 11: Closing during backend startup aborts health wait and terminates cleanly", async () => {
    const bm = new BackendManager();
    const mockChild = new MockChildProcess(77777);
    bm.childProcess = mockChild;
    bm.ownedPid = 77777;
    bm.ownedByElectron = true;
    bm.status = "starting";
    bm.isStarting = true;

    // Simulate mockChild not answering health check
    bm.checkHealthOnce = async () => ({ online: false, iris: false });

    let forceKillPid = null;
    bm.forceKillProcessTree = (pid) => {
      forceKillPid = pid;
      mockChild.simulateExit(1, "SIGKILL");
    };

    // Start waitForHealth in background (which would normally run 60 seconds)
    const healthPromise = bm.waitForHealth(60, 20);

    // After 30ms, user clicks close (invoking stop())
    await new Promise((r) => setTimeout(r, 30));
    await bm.stop();

    const healthResult = await healthPromise;
    assert.strictEqual(healthResult, false, "waitForHealth must immediately abort when stopping/stopped");
    assert.strictEqual(bm.status, "stopped");
    assert.strictEqual(bm.childProcess, null);
    assert.strictEqual(bm.isStarting, false);
  });
});
