# Política de Seguridad

## Versiones Soportadas

Utilizamos este proyecto para asegurar que se están utilizando las siguientes versiones:

| Versión | Soportada          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reportando una Vulnerabilidad

Si descubres una vulnerabilidad de seguridad dentro de este proyecto, por favor envía un correo electrónico al equipo del proyecto. Todas las vulnerabilidades de seguridad serán atendidas rápidamente.

### Proceso
1. Envía detalles de la vulnerabilidad por correo electrónico
2. Espera una confirmación, normalmente dentro de 48 horas
3. El equipo investigará y mantendrá comunicación sobre el progreso
4. Una vez resuelta, se publicará la corrección y se dará crédito si así se desea

Por favor, no divulgues públicamente la vulnerabilidad hasta que haya sido solucionada.

## Consideraciones de Seguridad Específicas

### Credenciales de API
- **OpenAI API**: Nunca almacenes tus claves de API en el código. Siempre usa variables de entorno o servicios de gestión de secretos.
- **Odoo API**: Las credenciales de Odoo deben manejarse con el mismo nivel de seguridad.

### Implicaciones de MCP
El Model Context Protocol (MCP) implica que las herramientas y datos están siendo expuestos a través de una API. Considera:
- Limitar el alcance de las herramientas expuestas a través de MCP
- Implementar autenticación adecuada para el servidor MCP
- Validar y sanitizar todas las entradas que provienen de la interacción con el usuario

### Datos Sensibles
Cuando desarrolles extensiones para este proyecto, ten en cuenta qué datos podrían exponerse inadvertidamente a través del agente conversacional:
- Información confidencial de clientes
- Datos financieros
- Información estratégica empresarial

## Mejores Prácticas
- Mantén todas las dependencias actualizadas
- Realiza auditorías de código regulares
- Implementa validación de entrada en todas las interfaces de usuario
- Limita los permisos del usuario de Odoo utilizado por la integración
