import numpy as np

predict = np.zeros((100, 100), dtype=np.uint8)
predict[20:80, 20:80] = 1

target = np.zeros((100, 100), dtype=np.uint8)
target[25:75, 25:75] = 1

print(predict.dtype)
E = np.abs(predict - target)
print(E.max())
