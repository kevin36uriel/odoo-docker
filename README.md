# Guía de Inicio Rápido: Levantamiento del Proyecto

Este proyecto utiliza **Docker Compose** para gestionar el entorno de desarrollo. Sigue estos pasos en orden para inicializar la base de datos con los módulos personalizados y levantar el sistema correctamente.

---

## Pasos para Levantar el Proyecto

Sigue atentamente estas instrucciones para realizar la primera carga limpia de la base de datos:

### 1. Preparar la Carga Inicial

Abre tu archivo `docker-compose.yml` y **descomenta la línea 16**. Esta línea contiene el comando específico para:

- Ejecutar una base de datos completamente limpia.
- Cargar e instalar todos los módulos personalizados de forma automática.

### 2. Ejecutar la Inicialización

En tu terminal, sitúate en la raíz del proyecto y ejecuta el siguiente comando para iniciar el contenedor:

```bash
docker compose up
```
