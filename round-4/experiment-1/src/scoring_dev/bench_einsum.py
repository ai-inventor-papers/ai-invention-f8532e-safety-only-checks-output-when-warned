import numpy as np, time
rng = np.random.default_rng(0)
L1, n, k = 29, 96, 40
G_EE = rng.standard_normal((L1, n, n))
G_EE = 0.5*(G_EE + G_EE.transpose(0,2,1))
C = rng.standard_normal((k, n))
K = rng.standard_normal((L1, 180, n))
c = rng.standard_normal(n)

N = 2000

t0=time.time()
for _ in range(N):
    proj_batch = np.einsum("lab,kb->lka", G_EE, C, optimize=True)
t1=time.time()
print("einsum proj_batch:", (t1-t0)/N*1000, "ms")

t0=time.time()
for _ in range(N):
    proj_batch2 = (G_EE @ C.T).transpose(0,2,1)
t1=time.time()
print("matmul proj_batch:", (t1-t0)/N*1000, "ms")
print("max diff:", np.max(np.abs(proj_batch - proj_batch2)))

W1 = rng.random((k, n))
t0=time.time()
for _ in range(N):
    num1 = np.einsum("lki,ki->lk", proj_batch, W1, optimize=True)
t1=time.time()
print("einsum num1:", (t1-t0)/N*1000, "ms")

t0=time.time()
for _ in range(N):
    num1b = (proj_batch * W1).sum(axis=-1)
t1=time.time()
print("bcast num1:", (t1-t0)/N*1000, "ms")
print("max diff:", np.max(np.abs(num1-num1b)))

t0=time.time()
for _ in range(N):
    num = np.einsum("lmn,n->lm", K, c, optimize=True)
t1=time.time()
print("einsum proj num:", (t1-t0)/N*1000, "ms")

t0=time.time()
for _ in range(N):
    num2 = K @ c
t1=time.time()
print("matmul proj num:", (t1-t0)/N*1000, "ms")
print("max diff:", np.max(np.abs(num-num2)))

t0=time.time()
for _ in range(N):
    den2 = np.einsum("n,lnk,k->l", c, G_EE, c, optimize=True)
t1=time.time()
print("einsum den2:", (t1-t0)/N*1000, "ms")

t0=time.time()
for _ in range(N):
    Gc = G_EE @ c
    den2b = (Gc*c).sum(-1)
t1=time.time()
print("matmul den2:", (t1-t0)/N*1000, "ms")
print("max diff:", np.max(np.abs(den2-den2b)))
