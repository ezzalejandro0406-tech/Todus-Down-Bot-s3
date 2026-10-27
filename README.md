# JK Bot — Telegram/YouTube a ToDus S3

Bot privado de Telegram que recibe documentos, vídeos, audios, fotos, reenvíos de Telegram y enlaces HTTP/HTTPS directos o páginas públicas compatibles con yt-dlp (incluido YouTube); todo archivo terminado se sube a ToDus S3 mediante `PUT` y devuelve un enlace público. No requiere cuenta ToDus, número de teléfono ni contraseña ToDus. Cada objeto queda bajo `users/tg_<ID>/telegram/...` y conserva una extensión segura (por ejemplo, `.apk` o `.mp4`).

## Estilo y uso

- El bot usa una estética de consola hacker con acentos verdes, separadores terminales, emojis y titulares en negrita. Las letras Unicode pequeñas son un efecto visual; Telegram no permite cambiar el tamaño tipográfico real.
- El inicio muestra nombre, @usuario e ID en la bienvenida. **Descargas** va en la fila superior; el resto del menú se organiza en filas de dos botones.
- Envía o reenvía un archivo, o pega un enlace HTTP/HTTPS en el chat privado. Las páginas públicas de vídeo se procesan con todos los extractores disponibles de la versión instalada de `yt-dlp`, por lo que cubre las redes sociales y plataformas que yt-dlp soporte en ese momento; no puede acceder a publicaciones privadas, cuentas con login, DRM o restricciones de la plataforma. Si una publicación pública no entrega medios con el perfil normal, el bot prueba un segundo perfil HTTP. Para contenido que la plataforma solo entrega tras iniciar sesión, configura `YTDLP_COOKIES_FILE` con un archivo Netscape privado y autorizado. Al terminar, el resultado muestra solo «El archivo se subió», con botones para descargar, copiar el enlace y convertir a TXT.
- YouTube se ejecuta con `yt-dlp-ejs` y Node.js para resolver los desafíos JavaScript actuales. Si YouTube exige confirmar que no eres un bot, el bot informa que debes configurar cookies autorizadas en `YTDLP_COOKIES_FILE`; no intenta saltarse el control.
- Los botones **Copiar enlace** usan el portapapeles nativo de Telegram y no envían mensajes adicionales. **Convertir TXT** manda al chat un archivo `.txt` con el nombre base del archivo y el/los enlace(s) de descarga dentro; no crea un enlace de descarga separado para el TXT.
- Antes de usar el bot, se verifica que el usuario pertenezca a `REQUIRED_CHANNEL` y `REQUIRED_GROUP`. El aviso indica exactamente qué chat falta y **Ya me uní** vuelve a comprobar la membresía antes de abrir el menú. Para verificar de forma fiable a otros usuarios, Telegram exige que el bot tenga permisos suficientes —normalmente administrador— en esos chats; si no, el bot muestra un diagnóstico y no concede acceso falso.
- Si un archivo se divide en partes, pulsa **Ver enlaces** para recibir todos sus vínculos juntos.
- `/ayuda` explica el uso; `/cola` muestra tareas activas y `/historial` abre resultados anteriores. El dueño puede usar `/backup` para enviar una copia cifrada inmediata y recibir un diagnóstico básico. El panel de administración incluye un reporte acumulativo de asignaciones de planes.
- En `/historial`, cada descarga aparece numerada. **Eliminar historial** permite borrar una entrada concreta o vaciar todos los registros con confirmación; en ambos casos se eliminan primero los objetos de ToDus S3 y después sus registros. Si ToDus falla, el historial se conserva para no perder los enlaces. Al completar el borrado total, el bot responde «El historial ha sido borrado con éxito».
- El botón **Pausar** detiene una tarea reanudable; **Reanudar** continúa usando las partes ya subidas y no empieza de cero. Al borrar un archivo de ToDus también se elimina su registro persistente.
- Cada usuario tiene una cola privada FIFO independiente. El límite es de 2 tareas para Gratis, 4 para VIP Básico, 8 para VIP Medio y 12 para Premium; el creador no tiene límite práctico de cola. La rotación entre usuarios evita que una persona bloquee a las demás.
- El botón **Top usuarios** y `/top` muestran los diez usuarios con más GB acumulados en la nube usando solo los últimos cuatro dígitos de su ID. `/jkadmin` incluye además el `@usuario`, el plan, el uso individual y el total acumulado de la comunidad.
- El bot funciona en chats privados. En grupos y canales permanece silencioso: no responde comandos, archivos, enlaces ni callbacks, y tampoco publica avisos automáticos de nuevas subidas. El chat de respaldo cifrado configurado es la única excepción técnica.
- Desde `/jkadmin` puedes abrir el historial de un usuario por ID, borrar una entrada concreta o todo su historial y eliminar sus objetos de ToDus S3. También existe **Borrar todo el historial**, que solicita confirmación y elimina los registros y objetos de nube de todos los usuarios.
- El panel incluye **Usuarios registrados**: muestra hasta 10 usuarios por página en una botonera `USER 1` a `USER 10`, con nombre completo, `@`, ID, cantidad de archivos y GB acumulados. Al tocar un usuario se abre su ficha e historial con acciones para borrar un archivo concreto o todo su contenido de ToDus S3.
- El menú principal muestra el saldo virtual. Cada usuario nuevo comienza con **5$**. En **Consultar planes** puede copiar su enlace personal o compartirlo; cuando una persona nueva entra con ese enlace, el invitado recibe su bienvenida de 5$ y el invitador recibe 5$ una sola vez. **Ver planes y comprar** siempre muestra todos los planes: los que no alcanzan el saldo aparecen bloqueados y no pueden confirmarse; los disponibles muestran una confirmación y descuentan el precio solo después de confirmar.
- El panel `/jkadmin` incluye **Dar saldo a un ID**: el dueño introduce el ID, el monto y confirma antes de guardar. El destinatario recibe una notificación con el monto acreditado y su nuevo saldo.
- Cuando una persona entra por un enlace de referido válido, el invitador recibe un aviso: «Alguien entró con tu enlace. ¡Felicidades! Recibiste 5$», junto con su saldo actualizado. Cada referido solo se recompensa una vez.
- Cada archivo subido recibe el TTL del plan activo: Gratis 12 horas, VIP Básico 24 horas, VIP Medio 48 horas, Premium 72 horas y Owner 72 horas. El enlace muestra la fecha/hora de expiración y un monitor elimina automáticamente el objeto de ToDus S3 cuando vence, incluso después de reiniciar el bot. La cuota Gratis se recarga cada 2 días; los demás planes, diariamente.
- **Mi cuota** muestra cuánto gastaste hoy, cuánto queda, una cuenta regresiva y la fecha/hora exacta del próximo reinicio en UTC. Al cambiar el día, los usuarios que usaron cuota reciben `✅ Cuota reiniciada con éxito` y su contador diario vuelve a cero; el acumulado del ranking no se borra.
- El bot registra en `users.json` a cada usuario que inicia o interactúa con él. **Estadísticas** usa ese registro para contar usuarios totales y activos del día. **Difusión** permite al dueño escribir un mensaje y enviarlo a todos los usuarios registrados con el encabezado «Mensaje del administrador»; los envíos fallidos se cuentan sin detener el resto.
- En una tarea activa puedes cancelar. Si se reanuda, las partes completadas se conservan; una parte interrumpida se vuelve a subir desde el inicio.

## Variables necesarias

<!-- Cambio documental de verificación de persistencia; no modifica la ejecución del bot. -->
<!-- Prueba de deploy inocua: no modifica el comportamiento del bot. -->

- `TELEGRAM_BOT_TOKEN`: token del bot creado con `@BotFather`. Es obligatorio. Por compatibilidad también se aceptan `TOKEN_BOT_DE_TELEGRAM`, `BOT_TOKEN` y `TELEGRAM_TOKEN`; configura solo uno.
- `TELEGRAM_BACKUP_CHAT_ID`: ID numérico o `@usuario` del canal o grupo de Telegram donde se publicará y fijará el respaldo cifrado. También se aceptan `BACKUP_CHAT_ID` o, como fallback, `TELEGRAM_CHANNEL_ID`. El bot debe poder enviar documentos allí; para fijar y reemplazar el mismo mensaje necesita permisos de fijado/edición.
- `TELEGRAM_BACKUP_INTERVAL_SECONDS`: intervalo del respaldo automático; por defecto son 300 segundos y el mínimo es 30.
- `TELEGRAM_API_ID` y `TELEGRAM_API_HASH`: opcionales; permiten descargar reenvíos de Telegram de más de aproximadamente 20 MiB. No sustituyen `TELEGRAM_BOT_TOKEN`.
- **No se configuran `TODUS_PHONE`, `TODUS_PASSWORD` ni credenciales de ToDus.**
- `REQUIRED_CHANNEL` y `REQUIRED_GROUP` indican los chats para comprobar membresía (por defecto `@gg_no_root` y `@videogameplay0406`). `CHANNEL_JOIN_URL` y `GROUP_JOIN_URL` indican los enlaces mostrados para unirse. El bot debe tener acceso suficiente para `getChatMember`; Telegram no garantiza la consulta de otros usuarios para bots no administradores.
- `YTDLP_COOKIES_FILE` es opcional: ruta a un archivo Netscape de cookies autorizado para publicaciones de Facebook/Instagram que no entregan el vídeo sin sesión. Mantén el archivo fuera de GitHub, no lo envíes al bot y usa solo cookies de una cuenta que tengas permiso de utilizar.
- `PLAN_ADMIN_USERNAME` es opcional y por defecto `jakudoshy`; controla el usuario que recibe las consultas de compra de planes.

### Respaldo y restauración Telegram

Configura `TELEGRAM_BACKUP_CHAT_ID` con el ID numérico o `@usuario` del chat de respaldo y agrega el bot con permiso para publicar, editar, borrar y fijar documentos. El bot consulta el chat y su mensaje fijado con la Bot API. Al iniciar, descarga, valida y restaura los archivos que falten **antes de abrir su sesión MTProto**; genera una copia inicial, otra después de cada cambio de datos, otra según `TELEGRAM_BACKUP_INTERVAL_SECONDS` y una última al cerrar de forma ordenada. Cada copia refleja exactamente los archivos de estado actuales: los historiales y sesiones eliminados localmente no se fusionan ni reaparecen desde una copia anterior. Las actualizaciones se suben como un documento cifrado nuevo, se leen y validan desde Telegram y se fijan antes de desfijar la versión anterior. La tarjeta del backup usa la hora local de Cuba.

El archivo único contiene los JSON de planes, cuotas, historial de tareas, caché local de recuperación y reporte administrativo acumulativo, además de la carpeta real de autenticación de Telegram `telegram_auth/` (sesión SQLite de Telethon cuando MTProto está configurado). Se comprimen los datos con gzip y se cifran con AES-256-GCM; la clave se deriva del `TELEGRAM_BOT_TOKEN`, sin una tercera variable. No se envían ni registran sesiones sin cifrar. Después de la primera copia, cada actualización reemplaza el documento del mismo mensaje fijado mediante `editMessageMedia`; si Telegram rechaza la edición, el bot borra la copia anterior y publica inmediatamente la nueva, manteniendo una sola copia visible y sin acumular spam. Los datos no se eliminan durante un deploy: solo cambian cuando una acción autorizada del bot los modifica. Los registros anteriores se mantienen dentro del JSON acumulativo. La Bot API alojada limita `getFile` a 20 MiB, así que una copia mayor se rechaza con su tamaño y la última copia válida queda intacta. Mantén el mismo token del bot para poder descifrar las copias existentes; al rotarlo, las copias anteriores no se podrán restaurar.

Este proyecto es un bot de Telegram: no usa Baileys ni tiene una carpeta `auth_info` de WhatsApp. La antigua sesión MTProto era solo de memoria; ahora, cuando se habilitan las credenciales MTProto opcionales ya documentadas, se guarda en `telegram_auth/` y se incluye cifrada. El token del bot sigue siendo el único requisito para el respaldo.

### Configurar API ID y API Hash en Railway

1. Abre [my.telegram.org](https://my.telegram.org) y entra en **API development tools** para obtener `api_id` y `api_hash`. Son credenciales de aplicación de Telegram, no el token de `@BotFather`.
2. En Railway, abre el proyecto y selecciona el servicio del bot.
3. En **Variables**, agrega `TELEGRAM_API_ID` y `TELEGRAM_API_HASH` con sus valores.
4. Confirma que `TELEGRAM_BOT_TOKEN` siga configurado, guarda los cambios y espera el redeploy.
5. Prueba primero un archivo pequeño y luego un reenvío grande de Telegram.

No pegues tokens ni hashes en el chat, el código o GitHub. Configura los valores privados en Railway.

## Archivos grandes y límites

La Bot API estándar de Telegram no descarga archivos mayores de aproximadamente 20 MiB. Para reenvíos grandes, configura juntos `TELEGRAM_API_ID` y `TELEGRAM_API_HASH`; si falta alguno, el bot indica cómo habilitarlos.

`MAX_FILE_SIZE_MIB` establece el límite de entrada (por defecto 4096 MiB). Los archivos que superen `MAX_PART_SIZE_MIB` (por defecto 1900 MiB) se dividen en archivos independientes, como `archivo.part001.ext`. **Ver enlaces** entrega las partes sin crear un teclado extenso.

Para recomponerlas, descarga todas las partes en la misma carpeta y únelas en orden. En Linux/macOS:

```bash
cat archivo.part* > archivo
```

En Windows, puedes usar 7-Zip para recomponer las partes según el tipo de archivo.

## Cola y almacenamiento

- `MAX_CONCURRENT_UPLOADS`: número de tareas procesadas simultáneamente.
- `MAX_PENDING_PER_USER`: cupo de tareas por usuario. La cola reparte turnos entre usuarios.
- Las tareas activas son temporales, pero el historial, cuotas, usuarios y `cloud_cache/` se guardan en `BOT_DATA_DIR`. En Railway debes montar un Volume en `/data`; sin un volumen ningún bot puede conservar archivos locales entre redeploys.
- Las subidas usan una ruta aleatoria dentro de `users/tg_<ID>/telegram/`; el nombre original se conserva como nombre de descarga, no como parte de la ruta.
- Los APK se validan como paquetes ZIP con `AndroidManifest.xml`, se sirven como `application/vnd.android.package-archive` y descarga adjunta; los MP4 se sirven como `video/mp4` y contenido reproducible en línea.
- Los documentos reenviados desde Telegram se descargan como bytes originales, conservan su nombre/MIME cuando Telegram los proporciona y se validan antes de subirlos; no se convierten ni se re-empacan.
- Si una web entrega un APK real con nombre `.zip`, el bot lo reconoce por `AndroidManifest.xml` y `classes.dex` y lo publica con extensión `.apk`. Los paquetes divididos XAPK/APKS se rechazan con un mensaje explicativo: requieren instalación dividida y no deben renombrarse como APK único.
- Solo se aceptan enlaces HTTP/HTTPS públicos. No se admiten URLs con credenciales ni direcciones locales/privadas. Para páginas de vídeo se usa yt-dlp, que cubre sus extractores/plataformas vigentes; los vídeos deben ser públicos y accesibles sin iniciar sesión, salvo que el administrador configure cookies autorizadas. No se pueden sortear restricciones de acceso, DRM ni bloqueos de la plataforma, y no se garantiza soporte para toda web. Los enlaces a archivos directos siguen descargándose por HTTP(S). Las páginas HTML sin un vídeo extraíble se rechazan en vez de guardarse como archivos diminutos.
- Una página de Play Store no es un APK descargable: el bot solo puede procesar un APK si recibe un enlace directo al archivo o el archivo reenviado. Una película de una aplicación como Movie Base solo se puede descargar si el enlace entrega un archivo reproducible sin DRM y sin controles de acceso; no se extraen ni se evitan protecciones de contenido.
- Si recibe una URL `play.google.com/store/apps/details?...`, el bot ahora lo explica directamente y no guarda la página HTML como si fuera una aplicación. Para instalar Firefox, por ejemplo, usa la ficha oficial de Play Store en el teléfono; para subir un APK al bot, envía el `.apk` o una URL directa y autorizada al archivo.

## Persistencia S3 y Cloud Guardian

TTL configurado: Gratis 12 horas, VIP Básico 24 horas, VIP Medio 48 horas, VIP Premium 72 horas y Owner 72 horas. El vencimiento se calcula al completar la subida y se conserva en el historial.

Todas las rutas de Telegram y YouTube convergen en `upload_to_todus_s3`; la descarga local solo es una etapa temporal antes del `PUT`. El plan Gratis conserva cada objeto durante 12 horas. Un monitor comprueba los enlaces cada minuto y, si ToDus deja de servir un objeto antes de su expiración, lo repone desde `cloud_cache/` sin sumar cuota ni ranking. La subida original sí suma bytes a cuota, historial y reporte acumulado; una reposición interna no duplica esos contadores. El caché se incluye en el respaldo de migración y se reconstruyen sus rutas al restaurar.

La persistencia real requiere configurar `BOT_DATA_DIR=/data` y un Volume de Railway. ToDus S3 es un servicio externo: el bot no puede garantizar una duración mayor que el TTL configurado si el proveedor elimina o bloquea objetos, pero el guardián detecta esa pérdida y reintenta la reposición mientras exista el caché.

## Ejecutar localmente

1. Copia `.env.example` a `.env` y configura `TELEGRAM_BOT_TOKEN`.
2. Para reenvíos de Telegram de más de ~20 MiB, agrega también `TELEGRAM_API_ID` y `TELEGRAM_API_HASH`.
3. Ejecuta:

   ```bash
   docker compose up -d --build
   docker compose logs -f
   ```

4. Abre el bot en Telegram, ejecuta `/start` y prueba con un archivo pequeño.

## Railway

Configura el repositorio `TELEGRAM_BOT_JK`, rama `main`, y verifica que el servicio tenga `TELEGRAM_BOT_TOKEN`. Añade `TELEGRAM_API_ID` y `TELEGRAM_API_HASH` solo si necesitas procesar reenvíos grandes. Tras el despliegue, abre `/ayuda` en Telegram.

La imagen Docker instala `ffmpeg` para combinar audio y vídeo cuando la plataforma los sirve por separado. Si ejecutas el bot fuera de Docker, instala también `ffmpeg` en el sistema. ToDus S3 es el único destino de almacenamiento de los archivos subidos. Telegram o una URL pública siguen siendo necesariamente la fuente de entrada; no se puede descargar un archivo desde ToDus si nunca fue subido allí.

Comparte únicamente archivos que tengas derecho a distribuir.

<!-- Deploy smoke-check: backup verification update. -->
