"""Streamlit GUI for the Newton-Raphson animation tool."""

import os
import tempfile
import threading
import time
from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
import sympy as smp
from matplotlib.animation import FFMpegWriter
from sympy.parsing.latex import parse_latex

from animation import NewtonRaphson
from constants import constants

st.set_page_config(page_title="Newton-Raphson Animation", layout="centered")


class RenderCancelled(Exception):
    """Raised inside report_progress to abort ani.save if "stop" is clicked."""

    pass


@dataclass
class Inputs:
    """
    Validated user input for a single render.

    Built by Gui.get_inputs() and consumed by Gui._render_worker()
    once is_valid() returns True.

    Attributes:
        tex_expr: The function as raw LaTeX, e.g. r"\\cos(x)".
        main_variable: The single variable being solved for e.g. "x".
        iterations: Number of steps to animate.
        x_coord_initial: Starting x-value for the iterations.
        parse_ok: Whether tex_expr was successfully parsed into a sympy expression.
        single_var_ok: Whether the parsed expression contains exactly one main variable.
        domain_ok: Whether the function is defined at x_coord_initial
            e.g. False for sqrt(x) with a negative starting point.
        constants: Built-in and user-defined constants substituted into
            the expression before evaluation e.g. {"pi": sympy.pi}.
    """

    tex_expr: str
    main_variable: str
    iterations: int
    x_coord_initial: float
    parse_ok: bool
    single_var_ok: bool
    domain_ok: bool
    constants: dict

    def is_valid(self):
        """Checks if each validation stage has passed and rendering can start."""
        return (
            self.tex_expr is not None
            and self.main_variable is not None
            and self.parse_ok
            and self.single_var_ok
            and self.domain_ok
        )


class Gui:
    """Streamlit front-end for Newton-Raphson animation.

    Gui() is re-instantiated on every Streamlit script rerun.
    Objects persisting across reruns, such as render progress,
    results, and errors live in st.session_state.
    """

    def __init__(self):
        pass

    def run_animation(self):
        """Renders input panels, "run"/"stop" button and output panels in that order."""
        inputs = self.get_inputs()

        if "is_running" not in st.session_state:
            st.session_state["is_running"] = False

        is_running = st.session_state["is_running"]
        label = "stop" if is_running else "run"

        st.write("")

        # disabled checks input validity
        # allows stop button to be clickable mid-render
        clicked = st.button(
            label, disabled=not inputs.is_valid(), width="stretch", type="primary"
        )

        if clicked:
            if is_running:

                # worker checks this once per frame in report_progress
                # worker exits on its own and can lag by one frame
                st.session_state["stop_event"].set()

            else:
                self.start_render(inputs)

                # redraw now so button flips to "stop"
                st.rerun()

        self.render_progress()
        self.error_banner()
        self.render_outputs()

    def get_inputs(self):
        """Collects and validates all user inputs: function, variable,
        iterations, starting point and constants. Renders the input form
        and any validation messages.

        Returns an Inputs instance regardless of validation outcome. Checks
        Inputs.is_valid() before rendering."""
        with st.container(border=True):
            tex_expr = st.text_input("Function (in LaTeX)", key="tex_expr") or None

            user_constants = self.constants_popover()
            all_constants = constants | user_constants

            expr, free_vars, parse_ok = None, [], False

            if tex_expr:
                try:
                    expr = parse_latex(tex_expr)

                    # substitute before counting free vars otherwise \pi counts as a var
                    expr = expr.subs(
                        {
                            sym: all_constants[str(sym)]
                            for sym in expr.free_symbols
                            if str(sym) in all_constants
                        }
                    )

                    free_vars_all = sorted(expr.free_symbols, key=str)
                    free_vars = [v for v in free_vars_all if str(v) not in constants]
                    parse_ok = True

                except Exception:
                    parse_ok = False

            single_var_ok = parse_ok and len(free_vars) <= 1
            main_variable = None

            if tex_expr:
                if not parse_ok:
                    st.caption(":red[Invalid LaTeX. Try again.]")
                elif not single_var_ok:
                    st.caption(":red[You can only have one main variable.]")
                else:
                    main_variable = str(free_vars[0]) if free_vars else "x"
                    st.caption(f"Using `{main_variable}` as the variable.")

        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True):
                iterations = st.slider(
                    "Iterations.",
                    min_value=1,
                    max_value=15,
                    value=5,
                    key="iterations",
                    disabled=not single_var_ok,
                )

        with col2:
            with st.container(border=True):
                label = (
                    f"Starting {main_variable}_0." if main_variable else "Starting x_0."
                )
                x_coord_initial = st.number_input(
                    label,
                    value=0.5,
                    key="x_coord_initial",
                    label_visibility="collapsed",
                    disabled=not single_var_ok,
                )

        domain_ok = True
        if parse_ok and main_variable:
            try:
                f_numeric = smp.lambdify(smp.Symbol(main_variable), expr, "numpy")
                result = f_numeric(x_coord_initial)
                domain_ok = bool(np.isfinite(result))

            except Exception:
                domain_ok = False

            if not domain_ok:
                phrase_1 = f"f({main_variable}) is undefined at {main_variable}\u2080 = {x_coord_initial}."
                st.error(phrase_1 + " Try a different starting point.")

        return Inputs(
            tex_expr,
            main_variable,
            iterations,
            x_coord_initial,
            parse_ok,
            single_var_ok,
            domain_ok,
            all_constants,
        )

    def constants_popover(self):
        """Renders a popover containing a read-only table of built-in
        constants (pi, e, ... ) and an editable table for user-defined constants.

        Returns the current user-defined constants as {name: value} rebuilt from the
        editor's current contents on every call.
        """
        with st.popover("Constants"):
            st.caption("Built-in: ")
            builtin_df = pd.DataFrame(
                [{"name": k, "value": str(v)} for k, v in constants.items()]
            )

            st.dataframe(builtin_df, hide_index=True, width="stretch")

            st.caption("Your constants. Add or remove below.")
            user_df = (
                pd.DataFrame(
                    [
                        {"name": k, "value": v}
                        for k, v in st.session_state.get("user_constants", {}).items()
                    ]
                )
                if st.session_state.get("user_constants")
                else pd.DataFrame(columns=["name", "value"])
            )

            edited = st.data_editor(
                user_df,
                num_rows="dynamic",  #  lets user add/delete rows
                hide_index=True,
                width="stretch",
                key="constants_editor",
            )

            new_constants = {}
            for _, row in edited.iterrows():
                name = str(row.get("name", "")).strip()
                val = row.get("value")

                # skip shadowing built-ins
                if name and name not in constants and val is not None:
                    try:
                        new_constants[name] = float(val)

                    except (TypeError, ValueError):

                        # row mid-edit
                        continue

            st.session_state["user_constants"] = new_constants

        return new_constants

    def start_render(self, inputs):
        """Starts a background thread to run the render.

        Keeps the UI responsive and the "stop" button clickable while
        ffmpeg encodes.
        """
        stop_event = threading.Event()

        # plain dict not session_state
        # worker has no ScriptRunContext to write session_state
        result_box = {"status": "running", "progress": (0, inputs.iterations)}

        thread = threading.Thread(
            target=self._render_worker,
            args=(
                inputs.tex_expr,
                inputs.main_variable,
                inputs.iterations,
                inputs.x_coord_initial,
                inputs.constants,
                stop_event,
                result_box,
            ),
            # don't block process exit
            daemon=True,
        )

        thread.start()

        st.session_state["render_thread"] = thread

        # since a later rerun needs to reach the same stop_event
        st.session_state["stop_event"] = stop_event
        st.session_state["result_box"] = result_box
        st.session_state["is_running"] = True

    def _render_worker(
        self,
        tex_expr,
        main_variable,
        iterations,
        x_coord_initial,
        constants_dict,
        stop_event,
        result_box,
    ):
        """Runs one full render (parse, validate, iterate and encode) on a
        background thread. Writes progress and results into result_box.

        Does not touch st.session_state directly. See render_progress()
        """
        fig = None  # set once create_plot() runs and guarded in finally
        tmp_path = None  # set once tempfile created and guarded in finally

        try:
            model = NewtonRaphson.get_inputs_anim(
                var=main_variable,
                func_as_tex=tex_expr,
                num=iterations,
                x_init=x_coord_initial,
                steps_per_line=10,  # frames per tangent/vertical segment
                constants=constants_dict,
            )

            ok, msg = self._check_stationary_point(model.df_num, model.x_coord, model.x)

            if not ok:
                result_box["status"] = "error"
                result_box["error"] = msg
                return

            model.find_x_n()

            x_sequence = [entry["x"] for entry in model.grad_and_c]
            ok, msg = self._check_convergence(x_sequence, model.f_num, model.x)

            if not ok:
                result_box["status"] = "error"
                result_box["error"] = msg
                return

            result_box["grad_and_c"] = model.grad_and_c
            result_box["main_variable"] = main_variable
            result_box["guess"] = model.guess

            ani = model.create_plot()
            fig = model.fig

            # delete=False so handle can be closed first to avoid OS permission errors on save
            tmpfile = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            tmp_path = tmpfile.name
            tmpfile.close()

            writer = FFMpegWriter(
                fps=20,
                codec="libx264",
                bitrate=-1,  # let ffmpeg auto-pick
                extra_args=["-preset", "ultrafast", "-pix_fmt", "yuv420p"],
            )

            def report_progress(current_frame, total_frames):
                if stop_event.is_set():
                    raise RenderCancelled()

                result_box["progress"] = (current_frame, total_frames)

            # lower dpi for faster encode
            ani.save(tmp_path, writer=writer, progress_callback=report_progress, dpi=80)

            with open(tmp_path, "rb") as f:
                result_box["video_bytes"] = f.read()

            result_box["status"] = "done"

        except RenderCancelled:
            result_box["status"] = "cancelled"

        except Exception as e:
            result_box["status"] = "error"
            result_box["error"] = str(e)

        finally:
            if fig is not None:
                plt.close(fig)

            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    @st.fragment(run_every=0.5)
    def render_progress(self):
        """Polls result_box for progress while a render is active.

        The worker thread cannot write st.session_state directly so this
        copies a finished result_box into session_state and triggers a rerun
        to update the UI.
        """
        if not st.session_state.get("is_running"):
            return

        result_box = st.session_state["result_box"]

        if result_box["status"] == "running":
            current, total = result_box["progress"]
            st.progress(
                current / total if total else 0,
                text=f"Creating animation ... Frames: {current}/{total}",
            )

        else:
            st.session_state["is_running"] = False

            if result_box["status"] == "done":
                st.session_state["video_bytes"] = result_box["video_bytes"]
                st.session_state["grad_and_c"] = result_box["grad_and_c"]
                st.session_state["main_variable"] = result_box["main_variable"]
                st.session_state["guess"] = result_box["guess"]
                st.session_state["last_error"] = None

            elif result_box["status"] == "cancelled":
                st.session_state["last_error"] = {
                    "level": "warning",
                    "msg": "Render stopped.",
                    "ts": time.monotonic(),
                }

            elif result_box["status"] == "error":
                error_msg = result_box["error"]
                st.session_state["last_error"] = {
                    "level": "error",
                    "msg": f"Failed to render video: {error_msg}",
                    "ts": time.monotonic(),
                }

            st.rerun()

    @st.fragment(run_every=0.5)
    def error_banner(self):
        """Shows the most recent error or warning for 3 seconds then clears it.

        Runs as its own timed fragment so banner expires independent
        of render_progress and other page reruns."""
        last_error = st.session_state.get("last_error")
        if not last_error:
            return

        if time.monotonic() - last_error["ts"] > 3:
            st.session_state["last_error"] = None
            return

        getattr(st, last_error["level"])(last_error["msg"])

    def render_outputs(self):
        """Displays the video, final root estimate and tangent equations table
        for the most recently completed render.
        """
        with st.container(border=True):
            st.caption("Matplotlib animation")
            video_bytes = st.session_state.get("video_bytes")
            grad_and_c = st.session_state.get("grad_and_c")
            main_variable = st.session_state.get("main_variable", "x")

            if video_bytes:
                st.video(video_bytes, autoplay=True, loop=False, muted=True)

                guess = st.session_state.get("guess")

                if not guess.is_Float:  # exact sympy root e.g. using \pi or \sqrt
                    st.text("Guess: ")
                    st.latex(f"{main_variable} = {smp.latex(guess)}")

                else:
                    st.text(f"{main_variable} = {float(guess):.4f}")

                dcol, rcol = st.columns(2)
                dcol.download_button(
                    "Download", video_bytes, file_name="iteration.mp4", width="stretch"
                )

                if rcol.button("Reset", width="stretch"):
                    st.session_state["video_bytes"] = None
                    st.session_state["grad_and_c"] = None
                    st.rerun()

                with st.expander("Tangent equations"):
                    self.render_iteration_table(grad_and_c, main_variable)
            else:
                st.caption(":gray[No animation yet - hit run.]")

    def render_iteration_table(self, grad_and_c, var):
        """Renders one row per iteration showing tangent line equation and resulting x value."""
        if not grad_and_c:
            return

        rows = []
        for step in grad_and_c:
            sign = "+" if step["c"] >= 0 else "-"
            eq = f"f({var})= {step['grad']:.4f}{var} {sign} {abs(step['c']):.4f}"
            rows.append(
                {
                    "iteration": step["iter"],
                    "equation": eq,
                    f"{var}\u2099": f"{step['x']:.4f}",
                }
            )

        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    def _check_stationary_point(self, df_num, x0, var, tol=1e-8):
        """Rejects a starting point where the derivative is zero or undefined.

        Newton-Raphson divides by f'(x0) so this is checked before iterating.
        """
        slope = float(df_num(x0))

        if not np.isfinite(slope) or abs(slope) < tol:
            phrase_1 = f"f'({var}\u2080) is zero or undefined at {var}\u2080."
            return (
                False,
                phrase_1 + " Try a different starting point.",
            )

        return True, None

    def _check_convergence(self, x_sequence, f_num, var, tol=1e-4):
        """Checks if the iteration converged near a root.

        If the sequence diverges or stays finite but there is no root nearby
        return False. Both are expected outcomes for a bad starting guess.
        """
        if any(not np.isfinite(x) for x in x_sequence):
            phrase_1 = "The sequence diverged to infinity or hit an undefined value."
            return (
                False,
                phrase_1 + " Often, this means there is no root in this area.",
            )

        final_residual = abs(f_num(x_sequence[-1]))
        if final_residual > tol:
            n = len(x_sequence) - 1
            return False, (
                f"After {n} iterations, f({var}) = {final_residual:.4f}. "
                "Usually, this means the function has no root near your starting point. "
                "Check if f crosses the x-axis or try a starting point close to the root."
            )

        return True, None
