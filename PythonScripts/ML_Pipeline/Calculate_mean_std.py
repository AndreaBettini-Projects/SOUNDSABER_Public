import numpy as np

X = np.load("X_train_raw.npy")

print("Shape:", X.shape)

mean = np.mean(X, axis=(0,1,2))
std = np.std(X, axis=(0,1,2))

print("Mean:")
print(mean)

print("Std:")
print(std)