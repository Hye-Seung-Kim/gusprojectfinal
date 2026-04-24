# Gus — Ambient Presence System

> "We miss Gus. So can we bring him back without actually bringing him back?"

## Concept

A two-location telepresence system that makes Gus (a dog at Kathy's house) feel present in the IxD Studio — not through an explicit interface, but as an **ambient, context-aware presence**. The system watches the studio, understands what's happening, and decides when and how Gus appears. Like a dog wandering into a room. The system is felt, not noticed.

---

## Two Locations

| Location | Role |
|---|---|
| **Kathy's House** | Pet camera captures Gus. Detects his presence and mood. Receives signals from the studio. |
| **IxD Studio** | Displays Gus on whiteboard/projector. Studio camera + mic reads human context. Sends context signals back. |

---

## System Architecture

### Layer 1 — Sense
- **Studio camera**: detects people, poses, proximity to display, group energy
- **Studio microphone**: noise level, talking vs. silence, crit vs. quiet work
- **Pet camera (Kathy's)**: Gus presence, Gus activity/mood

### Layer 2 — Understand (Context Model)
A continuously running model that answers:
- Is anyone in the studio right now?
- What's the energy level? (active crit, quiet focus, break, empty)
- Is anyone near the display area?
- Is Gus present and active at home?

### Layer 3 — Decide (Ambient Behavior Engine)
Rules / learned behavior that decides:
- Should Gus appear right now?
- How prominently? (full projection, faint overlay, just a shadow)
- For how long?
- What should happen at Kathy's house in response to studio state?

### Layer 4 — Respond (Implicit outputs)
**In the studio:**
- Gus fades in on the whiteboard when the room goes quiet or still
- Gus subtly orients toward someone who walks near the display
- Gus's energy/state mirrors the room's energy
- Gus disappears or shrinks when the room is loud/active

**At Kathy's house:**
- Soft light activates when a class gathering is detected
- Toy or sound triggers when "his people" are together
- Feedback signal when someone in the studio interacts near his display

---

## Design Principle

**Don't announce yourself.**

- No alerts. No buttons. No "Gus is online."
- No obvious agent behavior — no responses to commands, no UI
- Gus simply shows up when it feels right
- The interaction is implicit — proximity, stillness, presence
- Interventions at Kathy's house are gentle and deniable

---

## Build Phases

### Phase 1 — Detect Gus
- Pet camera feed → object/animal detection model
- Output: binary "Gus present / not present" signal
- Tools to explore: YOLOv8, MediaPipe, or a fine-tuned classifier

### Phase 2 — Segment Gus
- Background removal on Gus's camera feed in real time
- Output: clean Gus cutout (transparent background, live)
- Tools to explore: rembg, SAM (Segment Anything), OpenCV

### Phase 3 — Stream Data Between Locations
- Send cutout video + presence/mood signals from Kathy's house → studio
- Send studio context signals → Kathy's house
- Tools to explore: WebRTC, WebSockets, OSC (Open Sound Control)

### Phase 4 — Display Gus in the Studio
- Receive stream, render Gus on projector or large display
- Control opacity, scale, position based on behavior engine
- Tools to explore: Processing, TouchDesigner, a simple browser canvas app

### Phase 5 — Context Understanding (Studio Side)
- Camera + mic → real-time scene analysis
- Detect: number of people, proximity to display, noise level, group vs. solo
- Tools to explore: MediaPipe Pose, WebRTC audio analysis, Claude Vision API

### Phase 6 — Ambient Behavior Engine
- Rule-based or learned logic connecting context → output decisions
- "If room quiet for >2min and Gus present → fade Gus in at 40% opacity"
- "If someone within 1m of display → Gus orients toward them"
- Can start rule-based, evolve toward something trained on real interactions

### Phase 7 — Kathy's House Feedback
- Studio signals trigger gentle physical responses at home
- Options: smart light (Hue/WLED), servo-activated toy, soft audio cue
- Tools to explore: Raspberry Pi, MQTT, Home Assistant

---

## Open Design Questions

1. **How much agency does the system have?** Pure passive display vs. genuinely reading social context and deciding when to intrude vs. stay back.
2. **What is Gus's "vocabulary" of states?** Sleeping, alert, playful, calm — how does each translate to a studio presence behavior?
3. **How do you handle the absence of Gus?** What does the system do when Gus isn't on camera?
4. **What feedback does Kathy get?** Does she know the studio is "with" Gus right now?
5. **When does presence become intrusive?** There needs to be a threshold / suppression logic for crits, presentations, focused work.

---

## Reference Projects
- **Physical Telepresence** — Tangible Media Group, MIT Media Lab (tangible.media.mit.edu)
- Projection mapping on architectural surfaces (tiger projection refs in slide)
- Separate gesture zone concept (Tangible Media — physical proxy interaction)
