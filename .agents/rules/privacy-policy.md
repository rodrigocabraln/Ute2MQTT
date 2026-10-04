* Prohibido incluir datos sensibles reales en comentarios de código o ejemplos inline.
* Considerar “dato sensible” (no exhaustivo): usuarios, correos, teléfonos, documentos/IDs, cuentas bancarias, números de tarjeta, IBAN/SWIFT, tokens, API keys, cookies, sesiones, URLs con credenciales, direcciones exactas, montos de dinero (saldos, deudas, importes, facturas), y cualquier identificador personal o de cliente.
* Si necesitás dejar un ejemplo, usá placeholders o datos ficticios claramente irreales (ej.: <USER>, <EMAIL>, <ACCOUNT>, <AMOUNT>, <TOKEN>, <ID>).
* No pegar logs, dumps, respuestas de APIs, capturas o trazas que contengan datos sensibles sin sanitizar.
* Si detectás que ya existe información sensible en comentarios, eliminarla y reemplazarla por placeholders.

Ejemplos (NO hacer):
  * # Usuario: juan / Pass: 123456
  * # Cuenta: 001234567-0001 / Saldo: $ 156.114,00
  * # Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

Ejemplos (OK):
  * # Usuario: <USER> / Pass: <PASSWORD>
  * # Cuenta: <ACCOUNT> / Saldo: <AMOUNT>
  * # Token: <TOKEN>
