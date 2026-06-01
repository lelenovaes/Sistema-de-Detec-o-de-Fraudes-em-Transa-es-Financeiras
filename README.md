# Sistema-de-Deteccao-de-Fraudes-em-Transacoes-Financeiras
O sistema tem como objetivo analisar o arquivo logs_transacoes.txt, identificar possíveis fraudes financeiras e gerar um relatório web com gráfico e tabela.

1. Leitura dos Logs
O programa abre o arquivo de transações e lê todas as linhas registradas.

2. Extração dos Dados
A função analisar_transacao() transforma cada linha do log em um dicionário Python contendo informações como:
•	ID da transação 
•	Tipo da operação 
•	Origem e destino 
•	Valor 
•	Banco 
•	Localização 
•	Status 
•	Data e hora

3. Análise de Fraude
A função pontuar() aplica 8 regras de detecção de fraude:
-	Campos obrigatórios vazios. (25 pts)
-	Transações realizadas entre 00h e 04h. (20 pts)
-	Valores acima de R$ 20.000 (15 pts) ou R$ 50.000 (35 pts). 
-	Destinatários offshore ou internacionais suspeitos. (45 pts)
-	Banco destino de risco (código 380). (15 pts)
	Status da operação igual a FALHA. (20 pts)
-	Transações repetidas em até 5 minutos. (25 pts)
-	Descrição incompatível com o tipo da operação. (20 pts)
Cada regra adiciona pontos ao risco da transação.

4. Classificação do Risco
A pontuação é convertida em percentual e classificada em:
•	BAIXO: 0% a 30% 
•	MÉDIO: 31% a 60% 
•	ALTO: 61% a 100% 
Somente transações classificadas como MÉDIO ou ALTO são consideradas fraudes.

5. Geração das Estatísticas
O sistema conta:
•	Total de transações analisadas. 
•	Total de fraudes encontradas. 
•	Quantidade de riscos MÉDIO e ALTO. 
•	Frequência de cada tipo de fraude.

6. Criação da Página Web
O código gera automaticamente o arquivo relatorio_fraudes.html, contendo:
•	Cards com indicadores gerais. 
•	Gráfico de pizza mostrando os tipos de fraude detectados. 
•	Tabela com todas as operações suspeitas. 
•	Campo de busca e filtro por nível de risco.
