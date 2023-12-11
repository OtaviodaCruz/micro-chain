import matplotlib.pyplot as plt 
import numpy as np 

dataset = open("client_bad.txt", 'r')

y = []
xx = []

scale = False

sum_befor_scale = 0
qtd_befor_scale = 0

sum_after_scale = 0
qtd_after_scale = 0

for line in dataset:
    line = line.strip()

    if line == "--scale--":
        scale = True
    else:
        time, throughput, count_package, delay, empty = line.split(';')
    
        count = int(throughput)/1000
    
        y.append(count)
        xx.append(time)
    
        if not scale:
            sum_befor_scale = sum_befor_scale + count
            qtd_befor_scale = qtd_befor_scale + 1
        else:
            sum_after_scale = sum_after_scale + count
            qtd_after_scale = qtd_after_scale + 1

mean_befor_scale =  sum_befor_scale / qtd_befor_scale
mean_after_scale = sum_after_scale / qtd_after_scale

print("mean befor scale:", mean_befor_scale)
print("mean after scale:", mean_after_scale)

dataset.close()

x = list(range(len(y)))

print(y)

# create graph

plt.rcParams.update({'font.size': 12})

plt.bar(x, y)


plt.ylim(0, 8)
plt.xticks(np.arange(min(x), max(x)+1, 5.0))  # Set label locations.


plt.xlabel('Time')
plt.ylabel('Throughput (Kbps)')

#plt.axvline(23, color='red')

plt.show() 
