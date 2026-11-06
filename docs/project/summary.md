# When a single bit goes wrong: protecting a small computer chip from radiation

*Project summary for a general audience · Version 1 · 2 November 2026*

## The problem

Computer chips store information as billions of tiny on/off switches called bits. Particles from space, and the showers they create in the atmosphere, can hit a chip and flip one of those switches. Nothing breaks, but the stored value is now wrong. This is called a *soft error*.

On the ground this is rare. At aircraft cruising height it happens far more often, and in space more often still. A flipped bit can crash a flight computer, or worse, make it give a wrong answer that looks perfectly normal.

The usual fix is to build everything three times and take a vote. That works, but it makes the chip roughly three times bigger and more power-hungry. This project asks a cheaper question: **which parts of a processor actually matter when a bit flips, and what is the smallest protection that covers them?**

## What the project does

The project uses a small, free, open-source processor design called PicoRV32. Instead of real radiation, it uses computer simulation: run a program, flip one bit at a chosen moment, and see what happens. The program might still give the right answer, give a wrong answer, crash, or freeze.

Repeating this thousands of times will show which parts of the processor are most fragile. Then the project will try a few cheaper kinds of protection and compare them with the "build it three times" approach, counting both the reliability gained and the extra chip size and power.

Everything uses free tools, so anyone can repeat it.

## Where the project is today

**The first milestone is done, four days early.** Before breaking anything on purpose, the project had to prove that the simulated processor works perfectly when nothing goes wrong. That is now proven.

- **Five test programs are ready.** Each one is a small job typical of the kind of computers that matter here:
  1. multiplying tables of numbers,
  2. sorting a list,
  3. checking a block of data for corruption (the same check used in zip files and Ethernet),
  4. keeping an aircraft or satellite steady (a simple flight-control loop),
  5. checking aircraft position messages for errors (the ADS-B signals that planes broadcast).
- **Every answer was checked twice.** Each program's result matches a separate version written independently in Python.
- **The processor was checked step by step.** A separate "reference" model of the processor ran alongside the real design, and the two agreed on every single instruction in every program. Every one of the processor's 37 basic instructions was tested.
- **The check was shown to catch mistakes.** A deliberate error was planted, and the check caught it.
- **Boniface independently repeated the full check** and signed it off on 2 November.

## What comes next

| When | Milestone |
|---|---|
| by 27 Nov 2026 | Build the bit-flipping tool and run the first big experiment: a "map" of which parts of the processor are most fragile, for each of the five programs |
| by 18 Dec 2026 | Add five different kinds of protection, test them, and measure how much extra chip area and power each one costs |
| by 1 Jan 2027 | Charts, a short research paper, a demo app and a demo video |

No fault results exist yet. The project has only built and proven the starting point. Results will be added to this summary as they come in.

## Why it matters

If the answer turns out to be "only a few parts need protecting", designers of small processors for drones, aircraft and satellites could get most of the safety for a fraction of the cost. And because everything is free and open, others can check the work or reuse it.
