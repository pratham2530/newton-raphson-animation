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

  <img src="docs/images/add_user_constants.png" width="500" alt="Add user constants">

- Non-blocking and cancellable render

  <img src="docs/images/animation_mid_render.png" width="500" alt="Animation mid render">

- Final answer simplified to closed form where one exists (e.g. `sqrt(2)`,
  instead of `1.41421356...`)

  <img src="docs/images/figure.png" width="700" alt="Figure">

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

## Extensions (soon)

3D animation in Manim and/or Newton fractals. 
