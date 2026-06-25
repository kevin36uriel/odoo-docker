# 🚀 Guía de Inicio del Proyecto

README para levantar el entorno de desarrollo desde cero.

---

## 🛠️ Pasos para levantar el proyecto

### Paso 1 — Preparar la base de datos limpia

Abre el archivo `docker-compose.yml` y **descomenta la línea 16**.

Esta línea contiene el comando que inicializa la base de datos desde cero y carga los módulos personalizados. Debe verse algo así:

```yaml
# Antes (comentado):
# command: odoo -d odoo -i usuarios_iniciales,helpdesk_mgmt --stop-after-init --db_host=db --db_user=odoo --db_password=odoo

# Después (descomentado):
command: odoo -d odoo -i usuarios_iniciales,helpdesk_mgmt --stop-after-init --db_host=db --db_user=odoo --db_password=odoo
```

---

### Paso 2 — Ejecutar Docker Compose

Desde la raíz del proyecto, corre:

```bash
docker compose up
```

---

### Paso 3 — Esperar a que termine la inicialización

Observa la terminal. Cuando veas el mensaje:

```
exit(0)
```

Significa que la base de datos fue inicializada correctamente. En ese momento, detén la ejecución con:

```
Ctrl + C
```

---

### Paso 4 — Comentar la línea 16 y relanzar

Vuelve al archivo `docker-compose.yml` y **comenta nuevamente la línea 16** (como estaba originalmente).

Luego vuelve a ejecutar:

```bash
docker compose up
```

A partir de ahora el proyecto corre en modo normal, sin reiniciar la base de datos.

---

### Paso 5 — Iniciar sesión

Accede a la aplicación e inicia sesión con alguno de los siguientes perfiles:

| Perfil               | Descripción                             |
| -------------------- | --------------------------------------- |
| 👤 Usuario de prueba | Cuenta de testing con datos precargados |
| 🔑 Administrador     | Acceso completo al sistema              |

---

## ⚠️ Notas importantes

- Solo es necesario ejecutar el **Paso 1 al 3** la primera vez que se levanta el proyecto, o cuando se requiere un **reset completo** de la base de datos.
- En ejecuciones posteriores, basta con el **Paso 4 en adelante**.
- No dejes la línea 16 descomentada en ejecuciones normales: volvería a borrar y reinicializar la base de datos.
