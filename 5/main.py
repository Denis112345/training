import pandas as pd

d1 = {'a': [1, 2, 3], 'b': [None, 5, 6], 'c': [7, None, 9]}
d2 = {'b': [4, 89, 87], 'c': [54, 8, 35], 'd': [10, 11, 12]}

df1 = pd.DataFrame(d1)
df2 = pd.DataFrame(d2)

df3 = df1.fillna(df2).astype(int)

print(df3)