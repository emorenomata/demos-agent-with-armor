Tienes el siguiente objetivo:

1) Crear una chat de IA que responda consultas genericas, se busca que sea una demo para probar las capacidadades de Model Armor.
2) La arquitectura debe de ser simple, como Front Cloud Run protegido por Cloud Armor  para poder proteger accesos, ips y regiones. Luego Cloud Run accedera a preguntar a Gemini u otro modelo en Agent Plaform pero tiene que ser evaluado por Model Armor para proteger de Jailbreak, Datos Sensitivos, etc.
3) Al ser una demo, debe ser facilmente configurable el modelo, los templates de Model Armor a usar.
4) Usa la best practice de ADK y sigue el Scaffolding adecuado.
5) Toda esta estructura debe de poderse desplegar facilmente, por lo que crea el terraform de los servicios y bases.
6) Mantenlo simple, no hagas estructuras complejas. Esto debe poderse desplegar en el proyecto de GCP facil y tambien ser eleiminado.

Antes de aprobar la creacion, presenta el plan e incluso alguna sugerencia de interfaz como para habilitar y deshabilitar funciones o modelos.

