import sys, numpy as np
i = int(sys.argv[1])
sys.argv = ["ao_real.py", f"real{i}.npz", f"fin{i}"]
src = open("ao_real.py").read()
exec(src[:src.index('if __name__ == "__main__":')])
def mb(x, a=0.5):
    A = 2.0404*a - 0.3324; B = -4.7951*a + 0.6417; C_ = 2.7552*a + 0.6903
    return np.maximum(x, ((x*A + B)*x + C_)*x)
for R in (36, 128):
    a = mb(gtao(radius=R, thickness=0.5, maxdist=1e9))
    np.save(f"fin{i}_R{R}.npy", a.astype(np.float32))
print("done", i)
