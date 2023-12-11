import matplotlib.pyplot as plt 
import numpy as np 

dataset = open("server.txt", 'r')

y = []
xx = []
for line in dataset:
    line = line.strip()
    time, throughput, count_package, delay1, delay2, empty = line.split(';')
    
    count = int(throughput)/1000
    
    y.append(count)
    xx.append(time)

dataset.close()

x = list(range(len(y)))

print(y)

# create graph

plt.bar(x, y)

plt.ylim(0, 17)
plt.xlabel('Time')
plt.ylabel('Throughput (Kbps)')
plt.show() 
