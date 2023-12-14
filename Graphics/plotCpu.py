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
        
        metricsVectorPerMicro[micro]["cpu"].append(float(cpu))
        
        microPerTimer.append(micro)
        oldTime = currentTime
        first = False
    else:
        line = line.strip()
        micro, currentTime, cpu, memory, empty = line.split(';')
        
        if currentTime == oldTime:
            metricsVectorPerMicro[micro]["cpu"].append(float(cpu))
            microPerTimer.append(micro)
        else:
            # adiciona 0 para o microsserviço que não tem dado nesse tempo
            for microservice in microName:
                if not (microservice in microPerTimer):
                    metricsVectorPerMicro[microservice]["cpu"].append(0.0)

            microPerTimer = []
            
            metricsVectorPerMicro[micro]["cpu"].append(float(cpu))
            
            microPerTimer.append(micro)
            oldTime = currentTime
# escreve os dados vazios para o ultimo time
for microservice in microName:
    if not (microservice in microPerTimer):
        metricsVectorPerMicro[microservice]["cpu"].append(0.0)

dataset.close()

plt.rcParams.update({'font.size': 12})

# create graph
x = list(range(len(metricsVectorPerMicro[microName[0]]["cpu"])))
for microservice in metricsVectorPerMicro:
    plt.plot(x, metricsVectorPerMicro[microservice]["cpu"], label = microservice, marker='o')  

#plt.rcParams['legend.fontsize'] = 12
#plt.rcParams['xtick.labelsize'] = 16
#plt.rcParams['ytick.labelsize'] = 16
plt.xticks(np.arange(min(x), max(x)+1, 1.0))  # Set label locations.
plt.xlabel('Time')
plt.ylabel('CPU usage (in percent)')
plt.legend() 
plt.show() 
