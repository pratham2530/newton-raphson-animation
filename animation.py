"""Newton-Raphson iteration model and maplotlib animation builder."""

import matplotlib.pyplot as plt
import numpy as np
import sympy as smp
from latex2sympy2_extended import latex2sympy
from matplotlib.animation import FuncAnimation


class NewtonRaphson:
    """Builds and animates a Newton-Raphson root-finding seqeuence.

    Construct via get_inputs_anim(). Call find_x_n() to compute the iteration
    sequence and then create_plot() to build animation.
    """

    def __init__(self, x, func, num, x_init, consts, steps_per_line):
        self.x = x
        self.func = func
        self.num = num
        self.x_init = self.x_coord = x_init
        self.consts = consts
        self.steps_per_line = steps_per_line
        self.grad_and_c = []

        self.dfdx = smp.diff(self.func, self.x)
        self.f_num = smp.lambdify(self.x, self.func, "numpy")
        self.df_num = smp.lambdify(self.x, self.dfdx, "numpy")

        self.freeze_secs = 1
        self.playback_fps = 20

        self.zoomed_freeze_frames = 1 * self.playback_fps
        self.global_freeze_frames = 1 * self.playback_fps

    @classmethod
    def get_inputs_anim(
        cls, var, func_as_tex, num, x_init, steps_per_line, constants=None
    ):
        """Parses func_as_tex into a NewtonRaphson instance.

        Substitutes known constants before checking free symbols so
        expression reduces to zero or one free variable after.
        """
        constants = constants or {}
        x = smp.symbols(var, real=True)
        parsed = latex2sympy(func_as_tex)

        const_subs = {
            sym: constants[str(sym)]
            for sym in parsed.free_symbols
            if str(sym) in constants
        }
        parsed = parsed.subs(const_subs)

        free_syms = parsed.free_symbols
        if len(free_syms) == 1:
            parsed_var = free_syms.pop()
            func = smp.simplify(parsed.subs(parsed_var, x))

        elif len(free_syms) == 0:
            func = smp.simplify(parsed)

        else:
            raise ValueError(
                f"Expected one variable in the function. Found {free_syms}"
            )

        consts = [
            c for c in constants.values() if c.is_real
        ]  # nsimplify needs real numbers
        return cls(x, func, num, x_init, consts, steps_per_line)

    def find_new_x_coord(self):
        """Returns the new x_coord using Newton-Raphson."""
        numer = self.f_num(self.x_coord)
        denom = self.df_num(self.x_coord)

        if denom == 0:
            raise ZeroDivisionError

        return self.x_coord - numer / denom

    def find_x_n(self):
        """Runs the Newton-Raphson iteration and records the step history.

        Stops early on a zero or non-finite derivative, or a non-finite
        next-iterate. Sets self.guess to the final x_coord simplified to
        a closed form where one exists using self.consts."""
        for num in range(1, self.num + 1):
            curr_f = float(self.f_num(self.x_coord))
            curr_df = float(self.df_num(self.x_coord))

            if curr_df == 0 or not np.isfinite(curr_df):
                break

            c = curr_f - self.x_coord * curr_df  # y-intercept of tangent line
            x_coord_new = float(self.find_new_x_coord())

            if not np.isfinite(x_coord_new):
                break

            self.grad_and_c.append(
                {
                    "iter": num,
                    "grad": curr_df,
                    "c": c,
                    "x": x_coord_new,
                    "delta_x": x_coord_new - self.x_coord,
                }
            )

            self.x_coord = x_coord_new

        self.guess = smp.nsimplify(
            expr=self.x_coord, constants=self.consts, rational=False
        )

        return self.guess

    def update(self, frame):
        """FuncAnimation frame callback advances one drawing step.

        frame is decoded into segment, phase and index. Each step draws two
        segments consecutively: a vertical segment from the x-axis to the curve and
        then a tangent line to the x-axis. Once all steps are drawn, the view zooms
        towards each step's target region and then freezes on the final guess for
        1 second.
        """
        artists = []

        math_frames = self.num * self.steps_per_line * 2
        zoomed_freeze_end = math_frames + self.zoomed_freeze_frames

        current_segment = frame // self.steps_per_line
        current_phase = current_segment % 2  # 0 vertical, 1 tangent
        current_index = current_segment // 2  # which iteration the segment belongs to

        if current_phase == 0 and current_index < self.num:
            x_data, y_data = self.vertical_segments_data[current_index]
            progress = (frame % self.steps_per_line) / (self.steps_per_line - 1)
            self.vertical_segments[current_index].set_data(x_data, y_data * progress)
            artists.append(self.vertical_segments[current_index])

        elif current_phase == 1 and current_index < self.num:
            x_data, y_data = self.tangent_segments_data[current_index]
            progress = (frame % self.steps_per_line) / (self.steps_per_line - 1)

            (x_start, x_end), (y_start, y_end) = self.tangent_segments_data[
                current_index
            ]

            current_x = x_start + (x_end - x_start) * progress
            current_y = y_start + (y_end - y_start) * progress

            self.tangent_segments[current_index].set_data(
                [x_start, current_x], [y_start, current_y]
            )
            artists.append(self.tangent_segments[current_index])

        orig_xlim = self.orig_xlim
        orig_ylim = self.orig_ylim

        if frame < math_frames:
            if current_index < len(self.grad_and_c):
                step_info = self.grad_and_c[current_index]
                delta_x = abs(step_info["delta_x"])
                current_target_x = step_info["x"]
                current_target_y = float(self.f_num(current_target_x))

                if delta_x < 0.5:
                    zoom_width = max(delta_x * 4, 0.05)

                    target_xlim = [
                        current_target_x - zoom_width,
                        current_target_x + zoom_width,
                    ]
                    target_ylim = [
                        current_target_y - zoom_width,
                        current_target_y + zoom_width,
                    ]

                else:
                    target_xlim = orig_xlim
                    target_ylim = orig_ylim

            else:
                target_xlim = orig_xlim
                target_ylim = orig_ylim

            current_xlim = np.array(self.ax.get_xlim())
            current_ylim = np.array(self.ax.get_ylim())

            alpha = (
                1.0 if frame >= math_frames else 0.12
            )  # lerp speed towards target view

            new_xlim = current_xlim + alpha * (np.array(target_xlim) - current_xlim)
            new_ylim = current_ylim + alpha * (np.array(target_ylim) - current_ylim)

            self.ax.set_xlim(new_xlim)
            self.ax.set_ylim(new_ylim)

        elif zoomed_freeze_end >= frame >= math_frames:
            frame = math_frames - 1  # freeze on zoomed in frame

        else:
            self.ax.set_xlim(orig_xlim)
            self.ax.set_ylim(orig_ylim)

            self.final_vert.set_visible(True)
            self.final_label.set_visible(True)

            artists.extend([self.final_vert, self.final_label, self.point_label])

            for point_red, point_black in zip(self.red_points, self.black_points):
                point_red.set_visible(True)
                point_black.set_visible(True)
                artists.extend([point_red, point_black])

            frame = math_frames - 1

        return tuple(artists)

    def create_plot(self):
        """Builds static figure and returns a FuncAnimation over it.

        Must run after find_x_n() since it plots using self.guess
        and self.grad_and_c.
        """
        add = max(
            abs(float(self.x_init) - float(self.guess)) + 1, 3.0
        )  # view padding, min width 3

        self.x_vals = np.linspace(float(self.guess) - add, float(self.guess) + add, 400)
        func_np = smp.lambdify(self.x, self.func, "numpy")
        self.y_vals = func_np(self.x_vals)

        self.orig_xlim = [min(self.x_vals), max(self.x_vals)]
        self.orig_ylim = [min(self.y_vals) - 1, max(self.y_vals) + 1]

        self.fig, self.ax = plt.subplots()
        self.ax.set_xlim(self.orig_xlim)
        self.ax.set_ylim(self.orig_ylim)

        self.ax.axhline(y=0, color="black", linewidth=2, linestyle="-", alpha=0.5)

        self.ax.set(xlabel=str(self.x), ylabel=f"f({self.x})")

        self.ax.plot(
            self.x_vals,
            self.y_vals,
            label=f"f({self.x}) = {smp.pretty(self.func)}",
            color="blue",
        )

        # vertical line marking final guess shown at end
        self.final_vert = self.ax.axvline(
            x=self.guess, color="red", linestyle="--", alpha=0.5, visible=False
        )

        self.final_label = self.ax.text(
            x=self.guess,
            y=min(self.y_vals) * 0.9,
            s=f"{self.guess:.4f} (4.d.p)",
            ha="center",
            va="bottom",
            backgroundcolor="white",
            color="red",
            visible=False,
        )

        self.ax.grid(True)
        self.ax.legend()

        self.vertical_segments = []
        self.tangent_segments = []

        self.vertical_segments_data = []
        self.tangent_segments_data = []

        self.red_points = []
        self.black_points = []

        (red_point,) = self.ax.plot(
            [self.x_init],
            [0],
            "ro",
            markersize=6,
            picker=5,
            visible=False,
            zorder=3,  # keep dots in front of the curve
        )

        self.red_points.append(red_point)

        for iteration in self.grad_and_c:
            x_coord_prev = iteration["x"] - iteration["delta_x"]
            y_coord_prev = float(self.f_num(x_coord_prev))

            (tangent_segment,) = self.ax.plot([], [], "g-")
            self.tangent_segments.append(tangent_segment)

            self.tangent_segments_data.append(
                ((x_coord_prev, iteration["x"]), (y_coord_prev, 0))
            )

            (vertical_segment,) = self.ax.plot([], [], "r--")
            self.vertical_segments.append(vertical_segment)

            x_vert_data = np.array([x_coord_prev, x_coord_prev])
            y_vert_data = np.array([0, y_coord_prev])
            self.vertical_segments_data.append((x_vert_data, y_vert_data))

            (black_point,) = self.ax.plot(
                [x_coord_prev],
                [y_coord_prev],
                "ko",
                markersize=6,
                picker=5,
                visible=False,
                zorder=3,
            )

            self.black_points.append(black_point)

            (red_point,) = self.ax.plot(
                [iteration["x"]],
                [0],
                "ro",
                markersize=6,
                picker=5,
                visible=False,
                zorder=3,
            )

            self.red_points.append(red_point)

        self.point_label = self.ax.annotate(
            "",
            xy=(0, 0),
            xytext=(10, 10),
            textcoords="offset points",
            bbox=dict(boxstyle="round", fc="w", alpha=0.9),
            visible=False,
        )

        self.total_frames = (
            self.num * self.steps_per_line * 2
            + self.zoomed_freeze_frames
            + self.global_freeze_frames
        )
        ani = FuncAnimation(
            fig=self.fig,
            func=self.update,
            frames=self.total_frames,
            interval=10,
            blit=False,  # do not redraw artists to increase animation speed
            repeat=False,
        )

        return ani
