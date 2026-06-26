# Pump & MOSFET Breadboard Visual Guide

This is a visual map of the right side (f-j) of your breadboard based on your exact working setup. 
It shows exactly what plugs into which hole.

```text
     POWER RAILS           COMPONENT HOLES
     (+)      (-)        f    g    h    i    j
    ================    =========================
 30 | BATT+ | BATT- |  |    |    |    |    |    | 
 29 | WIRE+ |       |  | P+ |    |    | D- | W+ | <-- Pump+ and Diode Silver Band
 28 |       |       |  |    |    |    |    |    |
 27 |       |       |  |    |    |    |    |    |
 26 |       |       |  | P- |    | W↑ | D+ |    | <-- Pump-, Diode Black Band, Wire to MOSFET Drain
 25 |       |       |  |    |    |    |    |    |
 24 |       |       |  |    |    |    |    |    |
 23 |       | WIRE- |  |    |    |    |    |    | <-- Jumps from Row 22 to Ground Rail
 22 |       |       |  | MS | W↓ |    |    |    | <-- MOSFET Right Leg (Source)
 21 |       |       |  | MD | W↓ |    |    |    | <-- MOSFET Middle Leg (Drain)
 20 |       | R10K  |  | MG | R1 | R2 |    |    | <-- MOSFET Left Leg (Gate)
 .. |       |       |  |    |    |    |    |    |
 12 |       |       |  | R2 | W9 |    |    |    | <-- 220 Resistor from Row 20
 11 |       | WGND  |  |    |    |    |    |    | <-- Goes to Arduino GND
```

## Legend & Connections:

### 🔋 Power & Pump
* **BATT+ / BATT-** = The 4.5V Battery wires plugged into the rails.
* **P+** = Pump Positive (Red) wire.
* **P-** = Pump Negative (Black) wire.
* **WIRE+ (29 to 29j)** = A jumper wire giving Row 29 access to the Positive rail.

### 🔌 MOSFET & Diode
* **MG** = MOSFET Left Leg (Gate)
* **MD** = MOSFET Middle Leg (Drain)
* **MS** = MOSFET Right Leg (Source)
* **D-** = Diode Silver Band side (Cathode)
* **D+** = Diode Black side (Anode)

### 〰️ Jumpers & Resistors
* **W↑ / W↓ (26h to 21g)** = Jumper wire connecting Pump Negative to MOSFET Drain.
* **WIRE- (22g to 23-)** = Jumper wire grounding the MOSFET Source to the Negative rail.
* **R10K / R1** = The 10k Ohm Resistor. One leg goes in `20g`, the other goes to the Negative rail.
* **R2** = The 220 Ohm Resistor. One leg in `20h`, the other in `12f`.
* **W9** = Wire going from `12g` to Arduino Pin 9.
* **WGND** = Wire going from the Negative rail at row 11 to the Arduino GND pin.
