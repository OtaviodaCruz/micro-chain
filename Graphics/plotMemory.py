import matplotlib.pyplot as plt 
import numpy as np 

dataset = open("cpuAndMemory3.csv", 'r')

microName = []
for line in dataset:
    line = line.strip()
    micro, time, cpu, memory, empty = line.split(';')
    if not (micro in microName):
        microName.append(micro)

dataset.close()

metricsVectorPerMicro = {}
for micro in microName:
    metricsVectorPerMicro[micro] = {"cpu": [], "memory": []}

oldTime = ""
first = True
microPerTimer = []
dataset = open("cpuAndMemory3.csv", 'r')

for line in dataset:
    if first:
        line = line.strip()
        micro, currentTime, cpu, memory, empty = line.split(';')
        
        metricsVectorPerMicro[micro]["memory"].append(float(memory))
        
        microPerTimer.append(micro)
        oldTime = currentTime
        first = False
    else:
        line = line.strip()
        micro, currentTime, cpu, memory, empty = line.split(';')
        
        if currentTime == oldTime:
            metricsVectorPerMicro[micro]["memory"].append(float(memory))
            microPerTimer.append(micro)
        else:
            # adiciona 0 para o microsserviço que não tem dado nesse tempo
            for microservice in microName:
                if not (microservice in microPerTimer):
                    metricsVectorPerMicro[microservice]["memory"].append(0.0)

            microPerTimer = []
            
            metricsVectorPerMicro[micro]["memory"].append(float(memory))
            
            microPerTimer.append(micro)
            oldTime = currentTime
# escreve os dados vazios para o ultimo time
for microservice in microName:
    if not (microservice in microPerTimer):
        metricsVectorPerMicro[microservice]["memory"].append(0.0)

dataset.close()

# create graph
x = list(range(len(metricsVectorPerMicro[microName[0]]["memory"])))
for microservice in metricsVectorPerMicro:
    plt.plot(x, metricsVectorPerMicro[microservice]["memory"], label = microservice, marker='o')  

plt.xlabel('Time')
plt.ylabel('Memory usage (in percent)')
plt.legend() 
plt.show() 
