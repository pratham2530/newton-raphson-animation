# Newton-Raphson Animation

Streamlit app animating the Newton-Raphson method for a user-supplied
function. Enter a function in LaTeX, a starting point, and an iteration
count, then render the animation as an MP4.

Example animation: (*converted to a gif for the README*)

![Newton-Raphson animation](docs/demo.gif)

Input form: 

<img src="docs/images/input_form.png" width="500" alt="Input form">

## Features

- LaTeX input with validation: parse errors, multi-variable functions, and
  undefined starting points are rejected before render

  <img src="docs/images/error.png" width="500" alt="Error">
  
- Built-in constants

  <img src="docs/images/constants_table.png" width="500" alt="Constants table">
  
- Users can add constants via an editable table

  <img src="docs/images/add_user_constants.png" width="200" alt="Add user constants">

- Non-blocking and cancellable render

  <img src="docs/images/animation_mid_render.png" width="500" alt="Animation mid render">

- Final answer simplified to closed form where one exists (e.g. `sqrt(2)`,
  instead of `1.41421356...`)

  <img src="docs/images/figure.png" width="500" alt="Figure">

## Requirements

- Python 3.10+
- `ffmpeg` on `PATH` (system dependency  `FFMpegWriter` shells out to it directly)
- Python packages: see `requirements.txt`

## Getting started

```bash
pip install -r requirements.txt

streamlit run main.py
```

## Project structure

```
.
├── main.py           # launches GUI
├── gui.py             # streamlit front-end 
├── animation.py        # iteration sequence and matplotlib animation
└── constants.py         # built-in constants
```

## Notes

### Threading model

Streamlit reruns the full script on every interaction with no partial yield, so rendering inline would freeze the UI for the full encode time. Render runs on a background thread instead — `start_render()` spawns it and returns immediately, while the main thread keeps rerunning to draw progress and stay responsive to stop.

Streamlit only allows `st.session_state` writes from the main thread (tracked via `ScriptRunContext`, which spawned threads don't have), so the worker writes only to a plain dict, `result_box`. `render_progress()`, a `@st.fragment(run_every=0.5)`, is the only place that polls it and copies a finished result into session_state.

Cancellation is cooperative: stop sets a `threading.Event`, checked once per frame by FFMpegWriter's `progress_callback`, which raises `RenderCancelled` to unwind (can lag up to one frame). `daemon=True` keeps the worker from blocking process exit.

### Convergence behaviour
Newton-Raphson has quadratic convergence near a root so correct digits roughly double with each iteration. 
For most well-behaved functions, we do not need more than 10 iterations since floats carry 15-17 significant decimal digits. 
The ceiling of 15 is for  slower cases including starting values far from the root. 

#### Tolerances
`_check_stationary_point()`, tol=1e-8: rejects a derivative too close to zero
`_check_convergence()`, tol=1e-4: rejects a final residual not close enough to zero

### Encoding choices
GIF's 256-colour palette produces banding on anti-aliased matplotlib output but H.264 compresses continuous-tone renders way better. 
Since st.video() expects a video container, GIF would require st.image and would lose playback controls. 
ffmpeg exposes encoding controls that GIF encoders don't such as `-preset` ultrafast, `dpi=80` for encode speed, and `-pix_fmt yuv420p` for compatibility. 


## Extensions (soon)

3D animation in Manim and/or Newton fractals. 
