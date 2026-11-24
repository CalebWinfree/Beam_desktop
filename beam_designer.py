"""Beam Designer: preliminary beam analysis in a local Tkinter desktop app."""

from __future__ import annotations

import math
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk
from typing import Callable

E_KSI = 29_000.0
SHAPES = {
    "W10x22": dict(weight=22, depth=10.2, bf=5.75, tw=0.24, tf=0.36, ix=118, sx=23.2),
    "W12x26": dict(weight=26, depth=12.2, bf=6.49, tw=0.23, tf=0.38, ix=204, sx=33.4),
    "W14x30": dict(weight=30, depth=13.8, bf=6.73, tw=0.27, tf=0.385, ix=291, sx=42.0),
    "W16x31": dict(weight=31, depth=15.9, bf=5.53, tw=0.275, tf=0.44, ix=375, sx=47.2),
    "W21x44": dict(weight=44, depth=20.7, bf=6.50, tw=0.35, tf=0.45, ix=843, sx=81.6),
}


def fmt(value: float | None, digits: int = 2) -> str:
    if value is None or not math.isfinite(value):
        return "—"
    if abs(value) < 10**-digits:
        value = 0.0
    return f"{value:.{digits}f}"


def parse_number(raw: str, label: str, *, optional: bool = False,
                 positive: bool = False, nonnegative: bool = False) -> float | None:
    raw = raw.strip()
    if not raw and optional:
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{label} must be a finite number.") from exc
    if not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number.")
    if positive and value <= 0:
        raise ValueError(f"{label} must be greater than zero.")
    if nonnegative and value < 0:
        raise ValueError(f"{label} cannot be negative.")
    return value


@dataclass
class Load:
    kind: str
    magnitude: float
    load_class: str
    position: float = 0.0
    start: float = 0.0
    end: float = 0.0
    self_weight: bool = False


@dataclass
class Model:
    support: str
    span: float
    loads: list[Load]
    left_reaction: float
    right_reaction: float
    fixed_moment: float
    fixed_internal_moment: float


def resultants(loads: list[Load]) -> tuple[float, float]:
    force = moment = 0.0
    for load in loads:
        if load.kind == "point":
            force += load.magnitude
            moment += load.magnitude * load.position
        else:
            total = load.magnitude * (load.end - load.start)
            force += total
            moment += total * (load.start + load.end) / 2
    return force, moment


def make_model(support: str, span: float, loads: list[Load]) -> Model:
    force, moment = resultants(loads)
    if support == "simple":
        right = moment / span
        left = force - right
        fixed = 0.0
    else:
        left, right, fixed = force, 0.0, moment
    return Model(support, span, loads, left, right, fixed,
                -fixed if support == "cantilever" else 0.0)


def events(model: Model) -> list[float]:
    values = [0.0, model.span]
    for load in model.loads:
        values.extend([load.position] if load.kind == "point" else [load.start, load.end])
    values.sort()
    return [value for i, value in enumerate(values)
            if i == 0 or abs(value - values[i - 1]) > 1e-9]


def shear_at(x: float, side: str, model: Model) -> float:
    shear = model.left_reaction if (x > 0 or side == "after") else 0.0
    if model.support == "simple" and x == model.span and side == "after":
        shear += model.right_reaction
    for load in model.loads:
        if load.kind == "point":
            if load.position < x or (side == "after" and load.position == x):
                shear -= load.magnitude
        elif x > load.start:
            shear -= load.magnitude * (min(x, load.end) - load.start)
    return shear


def moment_at(x: float, model: Model) -> float:
    moment = model.fixed_internal_moment + model.left_reaction * x
    for load in model.loads:
        if load.kind == "point":
            if x > load.position:
                moment -= load.magnitude * (x - load.position)
        else:
            end = min(x, load.end)
            if end > load.start:
                moment -= load.magnitude * (
                    x * (end - load.start) - (end**2 - load.start**2) / 2)
    return moment


def peak(items: list[tuple[float, float]]) -> tuple[float, float]:
    return max(items, key=lambda item: abs(item[1])) if items else (0.0, 0.0)


def peak_shear(model: Model) -> tuple[float, float]:
    return peak([(x, shear_at(x, side, model))
                 for x in events(model) for side in ("before", "after")])


def peak_moment(model: Model) -> tuple[float, float]:
    candidates = [(x, moment_at(x, model)) for x in events(model)]
    xs = events(model)
    for start, end in zip(xs, xs[1:]):
        if end - start < 1e-10:
            continue
        mid = (start + end) / 2
        intensity = sum(load.magnitude for load in model.loads
                        if load.kind == "udl" and load.start < mid < load.end)
        if intensity > 1e-14:
            root = mid + shear_at(mid, "before", model) / intensity
            if start + 1e-9 < root < end - 1e-9:
                candidates.append((root, moment_at(root, model)))
    return peak(candidates)


def integrate_moment(model: Model, a_in: float, b_in: float,
                     x_eval_in: float | None = None, weighted: bool = False) -> float:
    if b_in <= a_in:
        return 0.0
    cuts = [a_in, b_in]
    cuts.extend(x * 12 for x in events(model) if a_in + 1e-9 < x * 12 < b_in - 1e-9)
    cuts.sort()

    def integrand(s_in: float) -> float:
        m_in = 12 * moment_at(s_in / 12, model)
        return (x_eval_in - s_in) * m_in if weighted else m_in

    total = 0.0
    for a, b in zip(cuts, cuts[1:]):
        total += (b - a) / 6 * (integrand(a) + 4 * integrand((a + b) / 2) + integrand(b))
    return total


def deflection_model(support: str, span: float, shape: dict,
                     loads: list[Load]) -> tuple[Model, Callable[[float], float], Callable[[float], float]]:
    model = make_model(support, span, loads)
    span_in = span * 12
    ei = E_KSI * shape["ix"]
    initial_slope = (integrate_moment(model, 0, span_in, span_in, True) / span_in / ei
                     if support == "simple" else 0.0)

    def slope(x_ft: float) -> float:
        x_in = x_ft * 12
        return initial_slope - integrate_moment(model, 0, x_in) / ei

    def deflection(x_ft: float) -> float:
        x_in = x_ft * 12
        return initial_slope * x_in - integrate_moment(model, 0, x_in, x_in, True) / ei

    return model, slope, deflection


def moment_roots(model: Model, start: float, end: float) -> list[float]:
    m0, mm, m1 = moment_at(start, model), moment_at((start + end) / 2, model), moment_at(end, model)
    quadratic = 2 * (m1 + m0 - 2 * mm)
    linear = m1 - m0 - quadratic
    scale = max(abs(m0), abs(mm), abs(m1), 1e-12)
    roots: list[float] = []

    def add(t: float) -> None:
        if math.isfinite(t) and 1e-10 < t < 1 - 1e-10:
            roots.append(start + t * (end - start))

    if abs(quadratic) <= scale * 1e-12:
        if abs(linear) > scale * 1e-12:
            add(-m0 / linear)
    else:
        disc = linear * linear - 4 * quadratic * m0
        if disc >= 0:
            root = math.sqrt(disc)
            add((-linear - root) / (2 * quadratic))
            add((-linear + root) / (2 * quadratic))
    return sorted(roots)


def peak_deflection(model: Model, slope: Callable[[float], float],
                    deflection: Callable[[float], float]) -> tuple[float, float]:
    xs = events(model)
    candidates = list(xs)
    for start, end in zip(xs, xs[1:]):
        partitions = [start, *moment_roots(model, start, end), end]
        for a, b in zip(partitions, partitions[1:]):
            fa, fb = slope(a), slope(b)
            if abs(fa) < 1e-12:
                candidates.append(a)
            if abs(fb) < 1e-12:
                candidates.append(b)
            if fa * fb >= 0:
                continue
            lo, hi = a, b
            flo = fa
            for _ in range(52):
                mid = (lo + hi) / 2
                fm = slope(mid)
                if abs(fm) < 1e-12:
                    lo = hi = mid
                    break
                if flo * fm <= 0:
                    hi = mid
                else:
                    lo, flo = mid, fm
            candidates.append((lo + hi) / 2)
    return peak([(x, deflection(x)) for x in candidates])


def solve(inputs: dict) -> dict:
    total_model = make_model(inputs["support"], inputs["span"], inputs["analysis_loads"])
    live_loads = [load for load in inputs["analysis_loads"] if load.load_class == "live"]
    total_def_model, total_slope, total_def = deflection_model(
        inputs["support"], inputs["span"], inputs["shape"], inputs["analysis_loads"])
    live_def_model, live_slope, live_def = deflection_model(
        inputs["support"], inputs["span"], inputs["shape"], live_loads)
    shx, shv = peak_shear(total_model)
    mx, mv = peak_moment(total_model)
    tx, tv = peak_deflection(total_def_model, total_slope, total_def)
    lx, lv = peak_deflection(live_def_model, live_slope, live_def)
    stress = 12 * abs(mv) / inputs["shape"]["sx"]
    allowed = 12 * inputs["span"] / inputs["divisor"]
    bending_ratio = stress / inputs["allowable"] if inputs["allowable"] is not None else None
    deflection_ratio = abs(lv) / allowed if inputs["has_live"] else None
    values = [total_model.left_reaction, total_model.right_reaction, total_model.fixed_moment,
              shv, mv, tv, lv, stress, allowed]
    values += [v for v in (bending_ratio, deflection_ratio) if v is not None]
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Inputs exceed the calculator's numeric range. Reduce the span or loads and try again.")
    return dict(model=total_model, shear=(shx, shv), moment=(mx, mv),
                total_deflection=(tx, tv), live_deflection=(lx, lv),
                total_def_model=total_def_model, live_def_model=live_def_model,
                total_def=total_def, live_def=live_def, stress=stress,
                allowable_deflection=allowed, bending_ratio=bending_ratio,
                deflection_ratio=deflection_ratio)


class ScrollFrame(ttk.Frame):
    """A vertically scrollable ttk content frame."""

    def __init__(self, master: tk.Misc, **kwargs):
        super().__init__(master, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0, background="#f3f6fa")
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.body = ttk.Frame(self.canvas, padding=10)
        self.window_id = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.body.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.window_id, width=e.width))


class PlotCanvas(tk.Canvas):
    def __init__(self, master: tk.Misc, painter: Callable[[tk.Canvas], None], **kwargs):
        super().__init__(master, height=190, background="white", highlightthickness=0, **kwargs)
        self.painter = painter
        self.bind("<Configure>", lambda _e: self.redraw())

    def redraw(self) -> None:
        self.delete("all")
        self.painter(self)


class BeamDesigner(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Beam Designer | Preliminary Beam Calculator")
        self.geometry("1400x940")
        self.minsize(1000, 700)
        self.configure(background="#f3f6fa")
        self.loads: list[dict[str, tk.Variable]] = []
        self.has_calculated = False
        self.last_inputs: dict | None = None
        self.last_results: dict | None = None
        self._style()
        self._build()
        self.section_canvas.bind("<Configure>", lambda _e: self._paint_section())
        for variable in (self.support_var, self.span_var, self.shape_var, self.allowable_var, self.divisor_var):
            variable.trace_add("write", lambda *_: self.mark_stale())
        self.load_example()

    def _style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#f3f6fa")
        style.configure("Panel.TFrame", background="white")
        style.configure("TLabel", background="#f3f6fa", foreground="#17243b", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 19, "bold"), foreground="#18345b")
        style.configure("Sub.TLabel", foreground="#64728a", font=("Segoe UI", 9))
        style.configure("Card.TLabel", background="white")
        style.configure("CardTitle.TLabel", background="white", foreground="#18345b", font=("Segoe UI", 11, "bold"))
        style.configure("TButton", padding=(9, 6))
        style.configure("Accent.TButton", background="#18345b", foreground="white", padding=(12, 7))
        style.map("Accent.TButton", background=[("active", "#2e69b3")])
        style.configure("TLabelframe", background="#f3f6fa", padding=10)
        style.configure("TLabelframe.Label", background="#f3f6fa", foreground="#18345b", font=("Segoe UI", 10, "bold"))

    def _build(self) -> None:
        header = ttk.Frame(self, padding=(20, 14))
        header.pack(fill="x")
        ttk.Label(header, text="Beam Designer", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="Educational calculator · Preliminary checks only", style="Sub.TLabel").pack(side="right")
        body = ttk.Frame(self, padding=(16, 0, 16, 16))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=0, minsize=360)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        self.inputs_scroll = ScrollFrame(body)
        self.inputs_scroll.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.results_scroll = ScrollFrame(body)
        self.results_scroll.grid(row=0, column=1, sticky="nsew")
        self._build_inputs(self.inputs_scroll.body)
        self._build_results(self.results_scroll.body)

    def _field(self, parent: ttk.Frame, label: str, variable: tk.Variable,
               row: int, col: int, width: int = 13) -> ttk.Entry:
        box = ttk.Frame(parent)
        box.grid(row=row, column=col, sticky="ew", padx=4, pady=4)
        ttk.Label(box, text=label, style="Sub.TLabel").pack(anchor="w")
        entry = ttk.Entry(box, textvariable=variable, width=width)
        entry.pack(fill="x", pady=(3, 0))
        return entry

    def _build_inputs(self, parent: ttk.Frame) -> None:
        group = ttk.LabelFrame(parent, text="Beam", padding=8)
        group.pack(fill="x", pady=(0, 9))
        self.support_var = tk.StringVar(value="Simply supported")
        ttk.Label(group, text="Support condition").grid(row=0, column=0, sticky="w", padx=4)
        ttk.Combobox(group, textvariable=self.support_var, state="readonly",
                     values=("Simply supported", "Cantilever")).grid(row=1, column=0, sticky="ew", padx=4, pady=(3, 8))
        self.span_var = tk.StringVar(value="20")
        self._field(group, "Span (ft)", self.span_var, 2, 0)
        ttk.Label(group, text="W-shape section").grid(row=4, column=0, sticky="w", padx=4, pady=(8, 0))
        self.shape_var = tk.StringVar(value="W12x26")
        shape_combo = ttk.Combobox(group, textvariable=self.shape_var, state="readonly", values=tuple(SHAPES))
        shape_combo.grid(row=5, column=0, sticky="ew", padx=4, pady=(3, 3))
        shape_combo.bind("<<ComboboxSelected>>", lambda _e: (self.draw_section(), self.mark_stale()))
        group.columnconfigure(0, weight=1)
        self.self_weight_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(group, text="Include beam self-weight as dead load", variable=self.self_weight_var,
                        command=self.mark_stale).grid(row=6, column=0, sticky="w", padx=4, pady=7)
        self.section_canvas = tk.Canvas(group, height=168, background="white", highlightthickness=1,
                                        highlightbackground="#dce3ed")
        self.section_canvas.grid(row=7, column=0, sticky="ew", padx=4, pady=(3, 0))
        ttk.Label(group, text="Schematic only · not to scale · thicknesses exaggerated; fillets omitted",
                  style="Sub.TLabel", wraplength=315).grid(row=8, column=0, sticky="w", padx=4, pady=4)

        check = ttk.LabelFrame(parent, text="Screening checks", padding=8)
        check.pack(fill="x", pady=(0, 9))
        self.allowable_var = tk.StringVar()
        self.divisor_var = tk.StringVar(value="360")
        self._field(check, "Allowable bending stress Fb (ksi, optional)", self.allowable_var, 0, 0)
        self._field(check, "Live-load deflection limit divisor n", self.divisor_var, 2, 0)

        loads_box = ttk.LabelFrame(parent, text="Applied loads", padding=8)
        loads_box.pack(fill="x", pady=(0, 9))
        buttons = ttk.Frame(loads_box)
        buttons.pack(fill="x", pady=(0, 7))
        ttk.Button(buttons, text="+ Point load", command=lambda: self.add_load("point")).pack(side="left", padx=(0, 5))
        ttk.Button(buttons, text="+ Uniform load", command=lambda: self.add_load("udl")).pack(side="left")
        self.load_rows_frame = ttk.Frame(loads_box)
        self.load_rows_frame.pack(fill="x")
        ttk.Label(loads_box, text="Point loads: kip at position (ft). Uniform loads: kip/ft over start and end (ft).",
                  style="Sub.TLabel", wraplength=315).pack(anchor="w", pady=(5, 0))

        ttk.Button(parent, text="Calculate results", style="Accent.TButton", command=self.calculate).pack(fill="x", pady=(1, 7))
        ttk.Button(parent, text="Load example beam", command=self.load_example).pack(fill="x")

    def _build_results(self, parent: ttk.Frame) -> None:
        self.status_var = tk.StringVar(value="Ready")
        status = ttk.Frame(parent)
        status.pack(fill="x", pady=(0, 6))
        ttk.Label(status, text="Analysis results", style="Title.TLabel").pack(side="left")
        ttk.Label(status, textvariable=self.status_var, style="Sub.TLabel").pack(side="right")
        self.error_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.error_var, foreground="#b74343", wraplength=850).pack(fill="x", pady=(0, 6))
        self.summary = ttk.LabelFrame(parent, text="Results summary", padding=10)
        self.summary.pack(fill="x", pady=(0, 9))
        self.summary_vars: dict[str, tk.StringVar] = {}
        keys = ["Reactions", "Peak shear", "Peak moment", "Peak deflection", "Live-load deflection",
                "Bending stress", "Deflection check", "Bending check"]
        for i, key in enumerate(keys):
            row, col = divmod(i, 2)
            card = ttk.Frame(self.summary, style="Panel.TFrame", padding=(9, 7))
            card.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
            ttk.Label(card, text=key, style="Sub.TLabel").pack(anchor="w")
            var = tk.StringVar(value="Enter beam data and calculate.")
            ttk.Label(card, textvariable=var, style="Card.TLabel", wraplength=380).pack(anchor="w", pady=(3, 0))
            self.summary_vars[key] = var
        self.summary.columnconfigure(0, weight=1)
        self.summary.columnconfigure(1, weight=1)

        section_frame = ttk.LabelFrame(parent, text="Beam and load diagram", padding=6)
        section_frame.pack(fill="x", pady=(0, 9))
        self.beam_plot = PlotCanvas(section_frame, self._paint_beam)
        self.beam_plot.pack(fill="x")
        for key, title in (("shear", "Shear diagram (kip)"), ("moment", "Moment diagram (kip-ft)"),
                           ("deflection", "Deflection diagram (in)")):
            box = ttk.LabelFrame(parent, text=title, padding=6)
            box.pack(fill="x", pady=(0, 9))
            plot = PlotCanvas(box, lambda c, kind=key: self._paint_chart(c, kind))
            plot.pack(fill="x")
            setattr(self, f"{key}_plot", plot)

    def add_load(self, kind: str, defaults: dict | None = None) -> None:
        defaults = defaults or {}
        try:
            default_span = float(self.span_var.get())
        except ValueError:
            default_span = 20.0
        if kind == "point":
            defaults.setdefault("position", default_span / 2)
        else:
            defaults.setdefault("start", 0)
            defaults.setdefault("end", default_span if default_span > 0 else 20)
        row = ttk.LabelFrame(self.load_rows_frame, text="Point load" if kind == "point" else "Uniform load", padding=6)
        row.pack(fill="x", pady=4)
        load: dict[str, tk.Variable] = {
            "kind": tk.StringVar(value=kind),
            "class": tk.StringVar(value=defaults.get("class", "Live")),
            "magnitude": tk.StringVar(value=str(defaults.get("magnitude", 2 if kind == "point" else 1))),
        }
        class_box = ttk.Frame(row)
        class_box.pack(fill="x", pady=(0, 4))
        ttk.Label(class_box, text="Load category").pack(side="left")
        ttk.Combobox(class_box, textvariable=load["class"], values=("Dead", "Live"), state="readonly", width=9).pack(side="left", padx=5)
        ttk.Button(class_box, text="Remove", command=lambda: self.remove_load(row, load)).pack(side="right")
        if kind == "point":
            load["position"] = tk.StringVar(value=str(defaults.get("position", 10)))
            fields = ttk.Frame(row)
            fields.pack(fill="x")
            self._field(fields, "Load (kip)", load["magnitude"], 0, 0)
            self._field(fields, "Position (ft)", load["position"], 0, 1)
        else:
            load["start"] = tk.StringVar(value=str(defaults.get("start", 0)))
            load["end"] = tk.StringVar(value=str(defaults.get("end", 20)))
            fields = ttk.Frame(row)
            fields.pack(fill="x")
            self._field(fields, "Intensity (kip/ft)", load["magnitude"], 0, 0)
            self._field(fields, "Start (ft)", load["start"], 1, 0)
            self._field(fields, "End (ft)", load["end"], 1, 1)
        for var in load.values():
            if isinstance(var, tk.StringVar):
                var.trace_add("write", lambda *_: self.mark_stale())
        self.loads.append(load)
        row._load_data = load  # type: ignore[attr-defined]
        self.mark_stale()

    def remove_load(self, row: ttk.LabelFrame, load: dict[str, tk.Variable]) -> None:
        row.destroy()
        if load in self.loads:
            self.loads.remove(load)
        self.mark_stale()

    def load_example(self) -> None:
        for child in self.load_rows_frame.winfo_children():
            child.destroy()
        self.loads.clear()
        self.support_var.set("Simply supported")
        self.span_var.set("20")
        self.shape_var.set("W12x26")
        self.self_weight_var.set(True)
        self.allowable_var.set("")
        self.divisor_var.set("360")
        self.add_load("udl", {"magnitude": 1, "start": 0, "end": 20, "class": "Live"})
        self.calculate()

    def mark_stale(self) -> None:
        if self.has_calculated:
            self.status_var.set("Inputs changed — calculate again")

    def read_inputs(self) -> dict:
        span = parse_number(self.span_var.get(), "Span", positive=True)
        assert span is not None
        support = "simple" if self.support_var.get() == "Simply supported" else "cantilever"
        shape_name = self.shape_var.get()
        if shape_name not in SHAPES:
            raise ValueError("Choose a supported W-shape.")
        shape = SHAPES[shape_name]
        loads: list[Load] = []
        for row in self.loads:
            kind = row["kind"].get()
            category = row["class"].get().lower()
            if category not in ("dead", "live"):
                raise ValueError("Choose dead or live for each load.")
            magnitude = parse_number(row["magnitude"].get(), "Point load" if kind == "point" else "Uniform load", nonnegative=True)
            assert magnitude is not None
            if kind == "point":
                position = parse_number(row["position"].get(), "Point-load position", nonnegative=True)
                assert position is not None
                if position > span:
                    raise ValueError("Point-load positions must be within the beam span.")
                loads.append(Load(kind, magnitude, category, position=position))
            else:
                start = parse_number(row["start"].get(), "Uniform-load start", nonnegative=True)
                end = parse_number(row["end"].get(), "Uniform-load end", nonnegative=True)
                assert start is not None and end is not None
                if start >= end:
                    raise ValueError("A uniform load's end must be greater than its start.")
                if end > span:
                    raise ValueError("Uniform-load positions must be within the beam span.")
                loads.append(Load("udl", magnitude, category, start=start, end=end))
        allowable = parse_number(self.allowable_var.get(), "Allowable bending stress", optional=True, positive=True)
        divisor = parse_number(self.divisor_var.get(), "Deflection-limit divisor", positive=True)
        assert divisor is not None
        analysis_loads = list(loads)
        if self.self_weight_var.get():
            analysis_loads.append(Load("udl", shape["weight"] / 1000, "dead", start=0, end=span, self_weight=True))
        return dict(span=span, support=support, shape=shape, shape_name=shape_name,
                    loads=loads, analysis_loads=analysis_loads,
                    include_self_weight=self.self_weight_var.get(), allowable=allowable,
                    divisor=divisor, has_live=any(l.load_class == "live" and l.magnitude > 0 for l in loads))

    def calculate(self) -> None:
        self.error_var.set("")
        try:
            inputs = self.read_inputs()
            results = solve(inputs)
        except (ValueError, OverflowError, ZeroDivisionError) as exc:
            self.error_var.set(str(exc))
            self.status_var.set("Analysis not updated")
            return
        self.last_inputs, self.last_results = inputs, results
        self.has_calculated = True
        self.status_var.set("Results updated")
        self._update_summary(inputs, results)
        for plot in (self.beam_plot, self.shear_plot, self.moment_plot, self.deflection_plot):
            plot.redraw()

    def _update_summary(self, inputs: dict, result: dict) -> None:
        model = result["model"]
        if inputs["support"] == "simple":
            reactions = f"Left {fmt(model.left_reaction, 3)} kip · Right {fmt(model.right_reaction, 3)} kip"
        else:
            reactions = f"Fixed reaction {fmt(model.left_reaction, 3)} kip · Moment {fmt(model.fixed_moment, 3)} kip-ft"
        self.summary_vars["Reactions"].set(reactions)
        sx, sv = result["shear"]
        mx, mv = result["moment"]
        tx, tv = result["total_deflection"]
        lx, lv = result["live_deflection"]
        self.summary_vars["Peak shear"].set(f"{fmt(abs(sv), 3)} kip at {fmt(sx)} ft from left")
        self.summary_vars["Peak moment"].set(f"{fmt(abs(mv), 3)} kip-ft at {fmt(mx)} ft from left")
        self.summary_vars["Peak deflection"].set(f"{fmt(abs(tv), 4)} in at {fmt(tx)} ft from left (total load)")
        self.summary_vars["Live-load deflection"].set(
            f"{fmt(abs(lv), 4)} in at {fmt(lx)} ft · limit {fmt(result['allowable_deflection'], 4)} in (L/{fmt(inputs['divisor'])})"
            if inputs["has_live"] else "0.0000 in · No live load; check not applicable")
        self.summary_vars["Bending stress"].set(f"{fmt(result['stress'], 3)} ksi · preliminary elastic stress")
        dr = result["deflection_ratio"]
        self.summary_vars["Deflection check"].set(
            "Not applicable (no live load)" if dr is None else
            f"DCR {fmt(dr, 3)} · {'PASS' if dr <= 1 else 'FAIL'} (user-selected screening limit)")
        br = result["bending_ratio"]
        self.summary_vars["Bending check"].set(
            "Enter Fb to compare; no pass/fail implied" if br is None else
            f"Fb {fmt(inputs['allowable'], 2)} ksi · DCR {fmt(br, 3)} · {'PASS' if br <= 1 else 'FAIL'}")

    def _base_axes(self, canvas: tk.Canvas, title: str) -> tuple[float, float, float, float]:
        w = max(canvas.winfo_width(), 400)
        h = max(canvas.winfo_height(), 150)
        left, right, top, bottom = 58, w - 22, 23, h - 30
        canvas.create_text(12, 10, text=title, anchor="nw", fill="#64728a", font=("Segoe UI", 9, "bold"))
        canvas.create_line(left, (top + bottom) / 2, right, (top + bottom) / 2, fill="#b9c4d3")
        canvas.create_line(left, top, left, bottom, fill="#dce3ed")
        return left, right, top, bottom

    def _paint_section(self) -> None:
        c = self.section_canvas
        c.delete("all")
        name = self.shape_var.get()
        if name not in SHAPES:
            return
        shape = SHAPES[name]
        width, height = max(c.winfo_width(), 280), max(c.winfo_height(), 160)
        center = width * 0.52
        top, depth, flange, web = 18, height - 38, 20, 22
        left, bottom = center - 66, top + depth
        dark, line = "#315f94", "#2e69b3"
        c.create_rectangle(left, top, left + 132, top + flange, fill=dark, outline=dark)
        c.create_rectangle(center - web / 2, top + flange, center + web / 2, bottom - flange, fill=dark, outline=dark)
        c.create_rectangle(left, bottom - flange, left + 132, bottom, fill=dark, outline=dark)
        c.create_line(left - 22, top, left - 22, bottom, fill=line, arrow="both")
        c.create_text(left - 28, (top + bottom) / 2, text=f"d = {shape['depth']:.2f} in", angle=90, fill="#17243b", font=("Segoe UI", 8))
        c.create_line(left, top + flange / 2, left + 132, top + flange / 2, fill=line, arrow="both")
        c.create_text(center, top + 4, text=f"bf = {shape['bf']:.2f} in", fill="#17243b", font=("Segoe UI", 8), anchor="n")
        c.create_line(center - web / 2, (top + bottom) / 2,
                      center + web / 2, (top + bottom) / 2, fill=line, arrow="both")
        c.create_text(center, (top + bottom) / 2 - 17, text=f"tw = {shape['tw']:.3f} in", fill="#17243b", font=("Segoe UI", 8))
        c.create_line(left + 145, bottom - flange, left + 145, bottom, fill=line, arrow="both")
        c.create_text(left + 150, bottom - flange / 2, text=f"tf = {shape['tf']:.3f} in", anchor="w", fill="#17243b", font=("Segoe UI", 8))
        c.create_text(width - 8, height - 5, text=f"{name} · {shape['weight']} lb/ft", anchor="se", fill="#64728a", font=("Segoe UI", 8))

    def draw_section(self) -> None:
        self._paint_section()

    def _paint_beam(self, c: tk.Canvas) -> None:
        left, right, top, bottom = self._base_axes(c, "Beam, supports, and applied loads")
        inputs = self.last_inputs
        if not inputs:
            return
        y = (top + bottom) / 2
        span = inputs["span"]
        x_at = lambda x: left + x / span * (right - left)
        c.create_line(left, y, right, y, fill="#18345b", width=5)
        if inputs["support"] == "simple":
            c.create_polygon(left - 11, y + 23, left, y + 2, left + 11, y + 23, fill="#8091a8", outline="#64728a")
            c.create_line(left - 15, y + 25, left + 15, y + 25, fill="#64728a")
            c.create_polygon(right - 11, y + 23, right, y + 2, right + 11, y + 23, fill="#8091a8", outline="#64728a")
            c.create_oval(right - 11, y + 24, right - 5, y + 30, fill="white", outline="#64728a")
            c.create_oval(right + 5, y + 24, right + 11, y + 30, fill="white", outline="#64728a")
            c.create_line(right - 17, y + 32, right + 17, y + 32, fill="#64728a")
        else:
            c.create_rectangle(left - 18, y - 18, left - 3, y + 20, fill="#8091a8", outline="#64728a")
            for yy in range(int(y - 15), int(y + 17), 8):
                c.create_line(left - 18, yy, left - 27, yy + 6, fill="#64728a")
        loads = inputs["loads"] + ([Load("udl", inputs["shape"]["weight"] / 1000, "dead", start=0, end=span, self_weight=True)] if inputs["include_self_weight"] else [])
        for i, load in enumerate(loads):
            color = "#e28a3b" if load.load_class == "live" else "#6481a8"
            if load.kind == "point":
                x = x_at(load.position)
                c.create_line(x, top + 12 + i % 2 * 8, x, y - 5, fill=color, width=2, arrow="last")
                kind = "L" if load.load_class == "live" else "D"
                c.create_text(x, top + 5 + i % 2 * 8, text=f"{fmt(load.magnitude)} kip {kind}", fill=color, anchor="s", font=("Segoe UI", 8))
            else:
                x1, x2 = x_at(load.start), x_at(load.end)
                yy = top + 19 + i % 2 * 8
                c.create_line(x1, yy, x2, yy, fill=color, width=2)
                count = max(2, min(12, round((x2 - x1) / 45)))
                for j in range(count + 1):
                    xx = x1 + (x2 - x1) * j / count
                    c.create_line(xx, yy, xx, y - 5, fill=color, arrow="last")
                kind = "L" if load.load_class == "live" else "D"
                c.create_text((x1 + x2) / 2, yy - 3, text=f"{fmt(load.magnitude)} kip/ft {kind}", fill=color, anchor="s", font=("Segoe UI", 8))
        c.create_text(left, bottom + 15, text="0 ft", fill="#64728a", anchor="w", font=("Segoe UI", 8))
        c.create_text(right, bottom + 15, text=f"{fmt(span)} ft", fill="#64728a", anchor="e", font=("Segoe UI", 8))

    def _paint_chart(self, c: tk.Canvas, kind: str) -> None:
        title = {"shear": "Total-load shear", "moment": "Total-load moment", "deflection": "Total and live-load deflection"}[kind]
        left, right, top, bottom = self._base_axes(c, title)
        inputs, result = self.last_inputs, self.last_results
        if not inputs or not result:
            return
        span = inputs["span"]
        zero = (top + bottom) / 2
        c.create_line(left, zero, right, zero, fill="#aebaca", dash=(3, 3))
        px = lambda x: left + x / span * (right - left)
        if kind == "shear":
            model = result["model"]
            pts: list[tuple[float, float]] = []
            ev = events(model)
            if ev:
                pts.append((ev[0], shear_at(ev[0], "before", model)))
                pts.append((ev[0], shear_at(ev[0], "after", model)))
            for a, b in zip(ev, ev[1:]):
                for j in range(1, 12):
                    x = a + (b - a) * j / 12
                    pts.append((x, shear_at(x, "before", model)))
                pts.extend([(b, shear_at(b, "before", model)), (b, shear_at(b, "after", model))])
            self._draw_series(c, pts, left, right, top, bottom, color="#2e69b3", x_map=px, scale_hint=max((abs(v) for _, v in pts), default=0))
            x, v = result["shear"]
            self._peak_label(c, px(x), v, fmt(abs(v), 3) + " kip")
        elif kind == "moment":
            model = result["model"]
            pts = self._sample(lambda x: moment_at(x, model), events(model), span)
            self._draw_series(c, pts, left, right, top, bottom, color="#2e69b3", x_map=px, scale_hint=max((abs(v) for _, v in pts), default=0), positive_down=True)
            x, v = result["moment"]
            self._peak_label(c, px(x), v, fmt(abs(v), 3) + " kip-ft", positive_down=True)
        else:
            total = result["total_def_model"]
            live = result["live_def_model"]
            ev = sorted(set(events(total) + events(live)))
            tpts = self._sample(result["total_def"], ev, span)
            lpts = self._sample(result["live_def"], ev, span)
            hint = max([abs(v) for _, v in tpts + lpts] or [0])
            self._draw_series(c, tpts, left, right, top, bottom, color="#2e69b3", x_map=px, scale_hint=hint, positive_down=True)
            self._draw_series(c, lpts, left, right, top, bottom, color="#e28a3b", x_map=px, scale_hint=hint, dash=(5, 3), positive_down=True)
            self._peak_label(c, px(result["total_deflection"][0]), result["total_deflection"][1], "Total", positive_down=True)
            if inputs["has_live"]:
                self._peak_label(c, px(result["live_deflection"][0]), result["live_deflection"][1], "Live", color="#b96c22", positive_down=True)
            c.create_line(right - 120, top + 8, right - 98, top + 8, fill="#2e69b3", width=2)
            c.create_text(right - 93, top + 8, text="Total", anchor="w", fill="#64728a", font=("Segoe UI", 8))
            c.create_line(right - 52, top + 8, right - 30, top + 8, fill="#e28a3b", width=2, dash=(5, 3))
            c.create_text(right - 26, top + 8, text="Live", anchor="w", fill="#64728a", font=("Segoe UI", 8))
        c.create_text(left, bottom + 14, text="0 ft", anchor="w", fill="#64728a", font=("Segoe UI", 8))
        c.create_text(right, bottom + 14, text=f"{fmt(span)} ft", anchor="e", fill="#64728a", font=("Segoe UI", 8))

    @staticmethod
    def _sample(function: Callable[[float], float], split: list[float], span: float) -> list[tuple[float, float]]:
        points: list[tuple[float, float]] = []
        coords = split or [0.0, span]
        points.append((coords[0], function(coords[0])))
        for a, b in zip(coords, coords[1:]):
            for i in range(1, 19):
                x = a + (b - a) * i / 18
                points.append((x, function(x)))
        return points

    @staticmethod
    def _draw_series(c: tk.Canvas, points: list[tuple[float, float]], left: float, right: float,
                     top: float, bottom: float, color: str, x_map: Callable[[float], float],
                     scale_hint: float, dash: tuple[int, ...] = (),
                     positive_down: bool = False) -> None:
        if not points:
            return
        max_abs = max(scale_hint, max(abs(v) for _, v in points), 1e-12)
        center = (top + bottom) / 2
        amplitude = (bottom - top) * 0.40
        coords: list[float] = []
        direction = 1 if positive_down else -1
        for x, value in points:
            coords.extend((x_map(x), center + direction * value / max_abs * amplitude))
        if len(coords) >= 4:
            c.create_line(*coords, fill=color, width=2, dash=dash, smooth=False)

    @staticmethod
    def _peak_label(c: tk.Canvas, x: float, value: float, text: str, color: str = "#18345b",
                    positive_down: bool = False) -> None:
        center = (23 + c.winfo_height() - 30) / 2
        positive_direction = 1 if positive_down else -1
        y = center + positive_direction * (1 if value >= 0 else -1) * min(42, c.winfo_height() * 0.22)
        c.create_oval(x - 3, y - 3, x + 3, y + 3, fill=color, outline="white")
        c.create_text(x + 5, y - 9, text=text, anchor="sw", fill=color, font=("Segoe UI", 8, "bold"))


if __name__ == "__main__":
    app = BeamDesigner()
    app.mainloop()
