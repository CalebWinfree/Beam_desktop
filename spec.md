# Beam Designer

## Purpose and limitations

Create a single-file Python desktop app using Tkinter that displays shear, moment, and deflection diagrams for a beam and provides preliminary bending-stress and deflection checks. Use Tkinter widgets for inputs and results, and a Tkinter Canvas for the beam illustration and diagrams. Run locally as a desktop window without a browser or web server. This is an educational calculator, not a substitute for a qualified engineer or a code-compliant design.

## First-release scope

- Analyze one straight, prismatic beam with either simply supported or cantilever end conditions.
- Assume static loading, linear-elastic material behavior, and small deflections.
- Support steel W-shapes only, bending about the strong axis.
- Do not analyze continuous beams, frames, or lateral-torsional/local buckling.

## Beam properties

- Use verified properties from AISC Shapes Database v15.0. The embedded curated set is W10x22, W12x26, W14x30, W16x31, and W21x44; record the source and release in `01_data/beam-catalog-source.md`.
- Do not invent or silently substitute missing properties.
- Store section name, weight per foot `W` (lb/ft), overall depth `d`, flange width `bf`, web thickness `tw`, and flange thickness `tf` (inches), strong-axis moment of inertia `Ix` (in^4), and strong-axis elastic section modulus `Sx` (in^3). Use steel elastic modulus `E = 29,000 ksi` (kip/in^2).
- Keep the app self-contained by embedding its supported beam catalog in the Python application file. Keep any source data or provenance files in `01_data/`.
- Do not include lumber in the first release.

## Inputs and units

- Support type, span in feet, and a W-shape selected from the supported catalog.
- Point loads in kips at a position in feet from the left end.
- Uniformly distributed loads in kip/ft, with start and end positions in feet. The start and end may define a partial-span load.
- Classify each applied load as dead or live.
- Include a self-weight toggle, on by default for catalog shapes; calculate self-weight from the selected shape's weight per foot and classify it as dead load.
- Use US customary units throughout. Display reactions and shear in kips, moment in kip-ft, deflection in inches, and bending stress in ksi.
- Treat applied point loads and distributed loads as downward-positive magnitudes; support reactions act upward. A point load may be at either endpoint or in the span. Require a distributed-load start `a` and end `b` with `0 <= a < b <= L`.
- Validate that spans and loads are finite, spans are positive, load positions are within the span, and distributed-load end positions exceed start positions. If `Fb` is entered, require a finite positive value; require the deflection divisor `n` to be finite and positive. Do not silently ignore invalid or unsupported input.

## Calculations and checks

- **Symbols:** `L` is the beam span; `x` is distance from the left end; `P` is a downward point-load magnitude; `w` is downward uniform-load intensity in kip/ft; `a` and `b` are its start and end positions; `R` is a support reaction in kips; `Mfix` is a cantilever's fixed-end reaction moment in kip-ft; `V(x)` is internal shear in kips; `M(x)` is internal bending moment (kip-ft in statics, kip-in in the deflection equation); `Mmax` is maximum absolute moment in kip-ft; `v(x)` is downward-positive deflection in inches; `v_live(x)` is deflection due to live loads only; `delta_allow` is the allowable deflection in inches; `fb` is calculated bending stress in ksi; `Fb` is user-entered allowable bending stress in ksi; `n` is the deflection-limit divisor; `DCRb` and `DCRd` are dimensionless bending and deflection ratios. Use feet for `L`, `x`, `a`, and `b` in input and statics calculations, and inches for beam-deflection calculations.
- **Self-weight:** Convert catalog weight to a dead-load intensity: `w_sw [kip/ft] = W [lb/ft] / 1000`.
- **Equilibrium and diagrams:** Calculate reactions from force and moment equilibrium, including the fixed-end reaction moment for a cantilever. A uniform load on `[a,b]` has resultant `w(b-a)` kips acting at `(a+b)/2`. With downward loads positive, use `dV/dx = -w` and `dM/dx = V` between load events; a downward point load causes a shear jump `V(x+) - V(x-) = -P`, with no moment jump. Include reaction jumps at the supports. Use sagging-positive internal moment.
- **Deflection:** For each load case, solve the small-deflection Euler-Bernoulli equation `E Ix d^2v/dx^2 = -M(x)` using downward-positive deflection and the selected support conditions. In this equation, `x` is in inches, `M(x)` is in kip-in, `E` is in kip/in^2, and `Ix` is in in^4. For a simply supported beam, deflection is zero at both supports and end moments are zero. For a cantilever, deflection and rotation are zero at the fixed end; at the free end, internal end actions must balance any load applied there (and are zero when no point load is applied at the tip). Superpose linear-elastic results to calculate live-load-only deflection and total dead-plus-live deflection. Convert lengths to inches, distributed loads from kip/ft to kip/in (`w_in [kip/in] = w [kip/ft] / 12`), and moments from kip-ft to kip-in before solving the deflection equation.
- **Peak results:** Report maximum absolute total-load shear and moment, plus maximum absolute total-load and live-load deflection, including each peak's position. Find extrema over the span, not just at load locations; check load-event locations and interior stationary points (for moment, where `V=0`; for deflection, where slope is zero).
- **Bending stress:** For a constant section, use the maximum absolute moment `Mmax` and strong-axis section modulus: `fb [ksi] = 12 |Mmax [kip-ft]| / Sx [in^3]`. The factor 12 converts kip-ft to kip-in, and kip/in^2 equals ksi. Allow the user to enter `Fb` in ksi; require `Fb > 0`. Calculate the dimensionless ratio `DCRb = fb/Fb` and show pass when `DCRb <= 1`, otherwise fail. If `Fb` is not provided, show stress without implying a pass.
- Treat the bending comparison as preliminary only. Do not infer allowable stress from steel grade or claim code compliance; the app does not check bracing, buckling, or design load combinations.
- **Deflection check:** Let the user configure the divisor `n` (default 360) and calculate `delta_allow [in] = 12 L [ft] / n`. Calculate the dimensionless ratio `DCRd = max|v_live| / delta_allow`; show pass when `DCRd <= 1`, otherwise fail. Show total-load deflection separately. If no live load is applied, report live deflection as zero and the live-load check as not applicable. Identify the limit as a user-selected screening criterion, not a universal code requirement.
- Do not provide a shear-strength pass/fail check in the first release. Report shear demand only.

## Outputs and presentation

- Present inputs and results in a clean, professional Tkinter window. Place the selected W-shape cross section near the beam selector, with dimension lines and values overlaid on the profile for `d`, `bf`, `tw`, and `tf`. Draw this cross-section on a Canvas and identify it as schematic, not to scale, with thicknesses exaggerated and fillets omitted.
- Draw the beam, supports, applied loads, and three labeled diagrams on Tkinter Canvas widgets: shear, moment, and deflection. Plot total-load deflection and distinguish the live-load-only curve used for its check.
- Show total-load support reactions (including a cantilever's fixed-end reaction moment), peak values and locations, bending stress and (when an allowable is entered) its ratio/result, and live-load deflection, limit, ratio, and result.
- Clearly indicate the selected section, units, self-weight setting, and any missing input needed for a check.
- Use standard Tkinter controls for load entry and results. Provide clear validation feedback in the window, keep the layout usable when resized, and load a valid example beam when the app opens.

## Validation

Compare results against hand calculations and test at least these cases:

1. **Simply supported UDL:** 20 ft W12x26 with a 1 kip/ft live load over the full span and self-weight on. Using `Ix ≈ 204 in^4` and 26 lb/ft nominal weight, reactions should be 10.26 kip each and maximum moment 51.3 kip-ft. Live-load deflection should be about 0.609 in; total-load deflection should be about 0.625 in. The live-load `L/360` limit is 0.667 in.
2. **Simply supported point load:** 10 ft W12x26 with a 2 kip midpoint load and self-weight off. Reactions should be 1 kip each, maximum moment 5 kip-ft, and maximum deflection about 0.0122 in.
3. **Cantilever UDL:** 10 ft W12x26 with a 1 kip/ft full-length load and self-weight off. The fixed-end reaction should be 10 kip, fixed-end moment 50 kip-ft, and free-end deflection about 0.365 in.

## Out of scope

Continuous or multi-span beams, lumber, point moments, dynamic loading, shear-capacity design, steel code design, LRFD load combinations, lateral-torsional buckling, local buckling, and code-compliance certification.
