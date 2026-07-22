import sympy as smp

# keys match the symbol name latex2sympy produces for each constant
# a mismatched key is skipped with no error and get_inputs_anim
# treats that constant as a free variable
constants = {
    "pi": smp.pi,
    "e": smp.E,
    "i": smp.I,
    "infty": smp.oo,
    "gamma": smp.EulerGamma,
    "phi": smp.GoldenRatio,
    "catalan": smp.Catalan,
    "sqrt_two": smp.sqrt(2),
    "sqrt_three": smp.sqrt(3),
    "sqrt_five": smp.sqrt(5),
}
