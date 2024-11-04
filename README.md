# Micro-Chain

This repository contain the code used in [1].

This work is an extension of [uNDN](https://github.com/Nayald/NDN-microservices) for multi-node scenarios, which are more complex.

## Setup

The experiments were executed in a cluster with 3 laptops. Laptop 1 (Master) has installed the K3s server, and Laptop 2 (Worker 1) and Laptop 3 (Work 2) has installed the K3s agent.

After installing K3s, the Manager, Web App and Prometheus are deployed in the Laptop 1. Similarly, the NDNperf client and NDNperf server are deployed, respectively, on Laptop 1 and Laptop 2.

### Details

For Prometheus, we used the [prometheus-community helm](https://github.com/prometheus-community/helm-charts) 

## Experiment 

Test the main operations using a scale scenario. The scenario consists of 3 laptops and 3 NDN microservices (*BR*, *NR*, *CS*), focusing on *BR* scaling.

You can watch a video that show a scaling up and down [here](https://youtu.be/LlY3qNmlDBs) 

### Basic commands:

Manager:

- ```kubectl exec -it <manager pod name> -- bash```
- ```python3 main.py```

Web app:

- Open ```http://<IP manager>:8080```
- Use the web application to manually deploy CS, BR and NR (New node)
- Create links: *CS* -> *BR* and *BR* - > *NR* (New link)

NDNPerf server:

- ```kubectl exec -it <NDNPerf server pod name> -- bash```
- ```ndnsec-keygen throughput | ndnsec-install-cert -```
- Starts NFD: ```nfd-start```
- ```nfdc face create tcp4://<IP NR>```
- ```nfdc route add localhop/nfd <FACE ID NR>```
- Starts the NDNPerf server: ```./ndnperfserver```

NDNPerf client:

- ```kubectl exec -it <NDNPerf cliet pod name> -- bash```
- ```nfdc face create tcp4://<IP BR>```
- ```nfdc route add throughput <FACE ID NR>```
- Starts the NDNPerf client: ```./ndnperf``` 

### References

[1] da Cruz, O. A. R., da Silva, A. A. S., Mendes, P. M., do Rosário, D. L., Cerqueira, E. C., dos Anjos, J. C. S., Pereira, C. E., & de Freitas, E. P. (2024). Micro-Chain: A Cluster Architecture for Managing NDN Microservices. Journal of Internet Services and Applications, 15(1), 424–437. https://doi.org/10.5753/jisa.2024.3965
