# Micro-Chain

This work is an extension of [uNDN](https://github.com/Nayald/NDN-microservices) for multi-node scenario.

## Setup

The experiments were executed in a cluster with 3 laptops. Laptop 1 (Master) has installed K3s server, and Laptop 2 (Worker 1) and Laptop 3 (Work 2) has installed K3s agent.

After install K3s, the Manager, Web App and Prometheus are deployed in the Laptop 1. Similarly, NDNperf client and NDNperf server are deployed, respectively, on Laptop 1 and Laptop 2.

### Details

For Prometheus, we used the [prometheus-community helm](https://github.com/prometheus-community/helm-charts) 

## Experiment 

Test the main operations using a scale scenario. The scenario consist in 3 laptops and 3 NDN microservices (*BR*, *NR*, *CS*), focusing on *BR* scaling.

Manager:

- ```kubectl exec -it <manager pod name> -- bash```
- ```python3 main.py```

Web app:

- Open http://<IP manager>:8080
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

- ```nfdc face create tcp4://<IP BR>```
- ```nfdc route add throughput <FACE ID NR>```
- Starts the NDNPerf client: ```./ndnperf``` 
