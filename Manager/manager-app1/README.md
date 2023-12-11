## Resumo
Possui o manager separado por modulos.
-> Testado com scaling BR
-> Não testado com outros scalings
-> Utiliza Prometheus para fazer a aquisição de informações de CPU e memória**
-> CS envia conteudo direto para o Prometheus
-> Manager adiquire hi_count e miss_count de CS

## Melhorias
-> Criar classes: graph e operations?