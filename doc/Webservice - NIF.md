Para facilitar a tarefa de validar programaticamente um nif, disponibilizamos uma simples api / webservice que permite, de forma fácil, gratuita e em tempo real, obter todas as informações de que dispomos.

Basta que utilize o endereço:

[http://www.nif.pt/?json=1&q=509442013&key=key](http://www.nif.pt/?json=1&q=509442013)

Não se esqueça de substituir o NIF acima pela expressão que pretende pesquisar.

Pode pedir [aqui](http://www.nif.pt/contactos/api/), a key necessária para utilizar a API

**Pesquisa**

_\- Pedido_

http://www.nif.pt/?json=1&q=509442013&key=key

_\- Resposta_

{"result": "success","records": {"509442013": {"nif": 509442013,"seo\_url": "nexperience-lda","title": "Nexperience Lda","address": "Rua da Lionesa Nº 446, Edifício G20","pc4": "4465","pc3": "671","city": "Leça do Balio","activity": "Desenvolvimento de software. Consultoria em informática. Comércio de equipamentos e sistemas informáticos. Exploração de portais web.","status": "active","cae": "62010","contacts": {"email": "info@nex.pt","phone": "220198228","website": "www.nex.pt","fax": "224 905 459"},"structure": {"nature": "LDA","capital": "5000.00","capital\_currency": "EUR"},"geo": {"region": "Porto","county": "Matosinhos","parish": "Leça do Balio"},"place": {"address": "Rua da Lionesa Nº 446, Edifício G20","pc4": "4465","pc3": "671","city": "Leça do Balio"},"racius": "[http://www.racius.com/nexperience-lda/](http://www.racius.com/nexperience-lda/)","alias": "Nex - Nexperience, Lda","portugalio": "[http://www.portugalio.com/nex/](http://www.portugalio.com/nex/)"}},"nif\_validation": true,"is\_nif": true,"credits": {"used": "free","left": \[\]}}

**Compra de créditos  
**  
Se ultrapassar os limites de utilização gratuita, poderá carregar a sua conta com créditos. Usando um pedido como exemplo abaixo, obterá os dados para pagamento, que poderá usar em qualquer caixa multibanco ou no seu homebanking. Os parâmetros invoice\_name e invoice\_nif não são obrigatórios (nestes casos, a fatura será emitida a "Consumidor Final"), mas se invoice\_nif for enviado, tem de ser um NIF válido.  

_\- Pedido_

http://www.nif.pt/?json=1&buy=1000&invoice\_name=Teste&invoice\_nif=123456789&key=key

_\- Resposta_

_{"credits": 1000,"mb": {"entity": "10241","reference": "000 000 000","amount": "10.00"}}  
_

**Verificação de Créditos  
**  
Para saber quantos créditos já gastou, sejam eles gratuitos ou pagos.  

_\- Pedido_

http://www.nif.pt/?json=1&credits=1&key=key

_\- Resposta_

_{"credits": {"month": 1000,"day": 100,"hour": 10,"minute": 1,"paid": 0}}  
_