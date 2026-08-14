# IRIS AI V4 — HOW IRIS WORKS
## An Intelligent Voice, Eye-Gaze & Desktop Assistant
*Tagline: See • Listen • Understand • Act • Verify • Recover*

![IRIS AI V4 General User Flowchart](file:///c:/Users/Meet%20Raval/IRISAI/iris_v4_general_user_flowchart.png)

---

## 1. Overview: How IRIS Works From a User's Perspective

IRIS AI V4 is designed as a hands-free, intelligent assistant for your computer. It allows you to control your desktop using **your voice** and **your eyes**, without needing to memorize complex hotkeys or manually click around the screen.

Unlike basic voice assistants that only answer questions, IRIS can actively interact with your applications—opening web browsers, typing search queries, clicking buttons, closing windows, and recovering automatically if an action fails.

---

## 2. The 9 Step Execution Journey

```
                        ┌────────────────────────┐
                        │          YOU           │
                        │  (Spoken / Eye Gaze)   │
                        └───────────┬────────────┘
                                    │
                                    ▼
                        ┌────────────────────────┐
                        │   IRIS LISTENS & SEES   │
                        │   (Microphone & Cam)   │
                        └───────────┬────────────┘
                                    │
                                    ▼
                        ┌────────────────────────┐
                        │     IRIS UNDERSTANDS   │
                        │  (Translates Intent)   │
                        └───────────┬────────────┘
                                    │
                                    ▼
                        ┌────────────────────────┐
                        │   IRIS CHECKS CONTEXT  │
                        │ (Scans Desktop State)  │
                        └───────────┬────────────┘
                                    │
                                    ▼
                        ┌────────────────────────┐
                        │    IRIS MAKES A PLAN   │
                        │  (Step-by-Step Steps)  │
                        └───────────┬────────────┘
                                    │
                                    ▼
                        ┌────────────────────────┐
                        │   IRIS CHECKS SAFETY   │
                        │ (Shield Policy Check)  │
                        └───────────┬────────────┘
                                    │
                                    ▼
                        ┌────────────────────────┐
                        │ IRIS PERFORMS ACTION   │
                        │ (App / Vision / Input) │
                        └───────────┬────────────┘
                                    │
                                    ▼
                        ┌────────────────────────┐
                        │  IRIS CHECKS WORK      │
                        │ (Visual Verification)  │
                        └───────────┬────────────┘
                                    │
                        ┌───────────┴────────────┐
                        │      DID IT WORK?      │
                        └─────┬────────────┬─────┘
                              │            │
                           YES│            │NO
                              ▼            ▼
                   ┌──────────────┐   ┌──────────────┐
                   │ TASK COMPLETE│   │ TRY AGAIN    │
                   │ (Voice Response) │ (Self-Recovery)
                   └──────────────┘   └──────┬───────┘
                                             │
                                             └────────► (Loops Back to Perform Action)
```

---

## 3. Detailed Step Breakdown

### Step 1: YOU (Multimodal Inputs)
You interact naturally with your computer:
- **Voice Commands:** Spoken instructions like *"Open Chrome"*, *"Search Python tutorials"*, *"Open Notepad"*, *"Click Save"*.
- **Eye-Gaze & Blinks:** Looking toward on-screen targets and performing deliberate double/long blinks to click or pause tracking.

### Step 2: IRIS LISTENS & SEES
- **Microphone:** Listens to your voice and filters background noise to ensure clear understanding.
- **Webcam Camera:** Tracks your facial position, detects 468 landmark points across your face, measures eye openness, and calculates exactly where your eyes are pointing on screen.

### Step 3: IRIS UNDERSTANDS
IRIS translates raw spoken words and eye movements into clear intentions. For example, if you say *"Open Chrome and search Python tutorials"*, IRIS breaks it down into distinct goals:
1. Open Google Chrome.
2. Focus the search bar.
3. Enter "Python tutorials".
4. Start the search.

### Step 4: IRIS LOOKS AT THE CURRENT SITUATION (Desktop Context)
IRIS looks at your active screen to understand references like *"Click it"* or *"Close this"*:
- Which window is currently active?
- Which application is running?
- What text or controls are currently visible?
- What text is copied to your clipboard?

### Step 5: IRIS MAKES A PLAN
Before clicking or typing, IRIS builds a simple step-by-step checklist to complete your request cleanly and logically.

### Step 6: IRIS CHECKS SAFETY
A built-in safety shield evaluates every planned action:
- Prevents rapid duplicate command triggers.
- Prompts for user confirmation if an action might affect critical data.

### Step 7: IRIS PERFORMS THE ACTION
IRIS uses a 3-tier reliable execution strategy:
1. **Tier 1 (Direct Control):** Communicates directly with the application's built-in accessibility controls for maximum speed and accuracy.
2. **Tier 2 (Visual Search):** Visually scans the screen to locate matching text labels or buttons if direct controls are unavailable.
3. **Tier 3 (Mouse & Keyboard Backup):** Uses smooth mouse movements and keyboard inputs as a dependable backup fallback.

### Step 8: IRIS CHECKS ITS WORK (Verification)
After performing an action, IRIS inspects the screen to confirm success:
- Did the requested window open?
- Is the application now active in the foreground?
- Did the expected screen change occur?

### Step 9: RESPONSE OR SELF-RECOVERY
- **If Successful (YES):** IRIS provides spoken voice confirmation (*"Done — Chrome opened and search completed"*) and updates the visual dashboard HUD.
- **If Something Went Wrong (NO):** IRIS automatically attempts self-recovery—re-focusing the window, retrying the step, or trying a backup interaction method—before asking for user assistance.

---

## 4. Real-World Usage Examples

### Example A: Voice Browser Search
1. **You Say:** *"IRIS, search Python tutorials"*.
2. **IRIS Listens & Understands:** Identifies application target (*Chrome*) and query (*Python tutorials*).
3. **IRIS Acts:** Opens Chrome, focuses the address bar, types *"Python tutorials"*, and presses Enter.
4. **IRIS Verifies & Responds:** Confirms Chrome is open with search results and speaks *"Done."*

### Example B: Hands-Free Eye Control
1. **You Look:** Glance toward a button or link on screen.
2. **IRIS Tracks:** Maps pupil position to the exact screen coordinate.
3. **You Blink:** Perform an intentional long blink.
4. **IRIS Acts:** Automatically moves the mouse cursor to the location and clicks the button.

---

## 5. Visual Dashboard & Optional Features

- **IRIS Dashboard & HUD:** A visual panel on your screen showing active status, eye-gaze tracking feedback, camera state, task execution progress, and system health.
- **Personalization & Learning:** Remembers your preferred settings, habits, and application choices over time to make future interactions faster and more personalized.
