# The Profile Cookbook

**A good profile is not "clean these rooms."**<br>
**A good profile is "handle this recurring moment."**

> The point of this whole system is to let you decide **once** and never carry it again. You think a routine through carefully one time, save it as a profile, and from then on the remembering lives in the vacuum, not your head.
>
> This page isn't about which buttons to press — that's [Profiles](10-profiles.md). It's about how to turn a *moment in your life* into a routine the vacuum runs for you.

## The idea: the vacuum works around your life

Most robot scheduling is backwards — you bend your day around when the machine runs. A profile flips it. Because a profile can **wait**, it can slot cleaning into the gaps of a real moment: after the meal, once the dog's dry, when you're already asleep.

The wait is the whole trick. **The wait is where the humanity lives.** A timer fires at a time; only a wait keyed to a *person* can say "after they've had enough of the evening" or "once you're actually under." Everything below is just learning to see those moments.

## Three knobs

Every profile is you turning three knobs around a moment:

- **Where** — the rooms, *in order*. Not a checklist — a **path**. Trace where the mess (or the person, or the pet) actually goes.
- **When** — the **wait**. Time it to a *transition*, not a clock for its own sake: the meal ending, the dog drying, you falling asleep, the rain passing.
- **How** — the **mode and water**. Match the *kind* of mess: mop a wet trail, vacuum dry fur or dust, go **low** water for damp drips so you're not adding more.

You build the steps in the Rooms view and save the sequence — the mechanics are all in [Profiles](10-profiles.md). This page is only about *what* to put in them.

## Worked examples

These are **mine** — my rooms, my house, my dog. Copy the *thinking*, not the rooms; yours will look nothing like mine, and that's exactly the point.

### Dinner — *the wait is the event*
Vacuum the kitchen and dining room → **wait 60 min** → vacuum-and-mop the same rooms. Clean before I cook, and then the wait simply *is* dinner, and the mop cleans up after we eat. One decision covers the whole meal.

### Wash Dog — *the rooms trace the path*
**Wait 45 min** while I'm out drying the dog → vacuum-and-mop the exit route, bathroom → hallway → living → dining (that leg is water, so it needs the mop) → **wait 60 min** while the dog finishes drying, shakes off, and wanders → clean the return route back through the living areas into the bedrooms, for the muddy paws and shed fur. The room *order* is the dog's actual path through the house.

### Post-visitor — *the run is the message*
When a guest arrives I flip a switch, and five hours later the vacuum heads out. It tidies up after them, sure — but the real job is the *gentle*, deniable signal that the evening's winding down, the thing you'd rather not say out loud. The dirt is the cover story.

### Bedtime — *the wait protects your sleep*
Kick it off at bedtime → **wait 2 hours** → clean the common areas. The wait isn't for the floor, it's for *you* — long enough that you're asleep before the noise starts, so the robot never wakes anyone.

### Rain / Wind — *the mode diagnoses the cause*
When the weather turns, the profile answers what it *does* to the house. **Rain** brings in leaves and drips → a **low-water** clean, because the floor's already damp and high water would only add to it. **Wind**, out in the country, blows in dry field dust → a plain vacuum, no water at all. Same rooms, different *how*, because the cause is different.

## Find your own moments

You won't reuse my profiles — you'll reuse the **questions**:

- What in your home has a **before / during / after**? A meal, a bath, guests, the workday, the school run.
- What **path** does the mess take? Follow it room by room — that's your *where*, and its *order*.
- What are you **waiting for** — a person, a pet, the weather, sleep? That's your *when*.
- What **kind** of mess is it — wet, dry, damp? That's your *how*.

Answer those once, per moment, and you've built something you'll use for years without thinking about it again. That's the whole trade: think hard for five minutes, reuse it for as long as it holds true.

## Triggering it — boring, on purpose

How a profile *starts* is deliberately dull, because it's as personal as the profile itself. Wire it to whatever you already have:

- **On demand** — tick *Expose as Home Assistant Button* and the profile becomes a button entity; or drop the [Profile card](20-dashboard-and-room-cards.md#the-profile-card) on a dashboard; or say it to a voice assistant. A wall switch whose only job is "send the vacuum out" works just as well.
- **On a clock** — a time or calendar automation calling `eufy_vacuum.start_run_profile` (see [Automation examples](../advanced/04-automation-examples.md)).
- **On a condition** — presence, a scene, a weather entity — any sensor or trigger you like, calling that same service.

And because the **wait absorbs the slack**, the trigger can be coarse: you don't have to catch the exact moment, just nudge it in the right neighbourhood and let the profile carry the rest.
