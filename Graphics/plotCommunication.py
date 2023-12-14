import matplotlib.pyplot as plt 
import numpy as np 

dataset = open("communication3.csv", 'r')

y = []
xx = []
for line in dataset:
    line = line.strip()
    time, udp_count_receive, udp_byte_receive, udp_count_send, udp_byte_send, monitor_count_receive, monitor_byte_receive, monitor_count_send, monitor_byte_send, k8s_count_receive, k8s_byte_receive, k8s_attempt_receive, k8s_count_send, k8s_byte_send, k8s_attempt_send, empty = line.split(';')
    
    count = int(udp_count_receive) + int(udp_count_send) + int(monitor_count_receive) + int(monitor_count_send) + int(k8s_count_receive) + int(k8s_count_send)
    
    y.append(count)
    xx.append(time)

dataset.close()

x = list(range(len(y)))

for i in x:
    print(i, y[i])

# create graph

plt.plot(x, y, label = "Communication count", marker='o')  

#plt.xticks(rotation = 45)
plt.ylim(0, 50)
plt.xlabel('Time')
plt.ylabel('Amount of Communication')
plt.show() 
