# Beam catalog source

The embedded section dimensions and strong-axis properties are a curated subset of the **AISC Shapes Database v15.0**. AISC describes v15.0 as the electronic companion to the 15th Edition Steel Construction Manual, with section dimensions and properties in US customary and metric units.

Source: [AISC, 15th Edition Steel Construction Manual resources](https://www.aisc.org/aisc/publications/steel-construction-manual/15th-ed-steel-construction-manual/)

The application embeds these W-shapes: W10x22, W12x26, W14x30, W16x31, and W21x44. Embedded fields are nominal weight per foot, depth, flange width, web thickness, flange thickness, strong-axis moment of inertia `Ix`, and strong-axis elastic section modulus `Sx`. The values are in US customary units and appear in `beam_designer.py`.

This catalog is for the educational calculator only. Confirm section properties against the applicable AISC database and project requirements before engineering use.
