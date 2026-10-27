# Investigación Play Store y APK

- Google Play Internal App Sharing: https://support.google.com/googleplay/android-developer/answer/9844679?hl=en
  - Permite compartir APK/AAB que el propietario sube desde Play Console con testers autorizados o mediante enlace.
  - Los enlaces de Internal App Sharing caducan a los 60 días.
  - Es un flujo para artefactos propios/autorizados, no una descarga arbitraria desde una ficha pública.

- Google Play Developer API: https://developers.google.com/android-publisher/api-ref/rest/v3/edits.apks/download
  - La API de APK está orientada a aplicaciones y ediciones bajo control del desarrollador autenticado.
  - No constituye un método general para convertir cualquier URL pública de Play Store en un APK descargable.

- EFF apkeep: https://github.com/EFForg/apkeep
  - Proyecto MIT que soporta fuentes Google Play, F-Droid y APKPure.
  - Para Google Play requiere email y AAS token; advierte que apps pagadas y con DRM no están disponibles y que el uso debe respetar los términos de Google.
  - Puede evaluarse como integración opcional para apps autorizadas, pero requiere credenciales y configuración del usuario; no se incorporó automáticamente al bot.

Conclusión: el bot debe seguir rechazando una ficha pública de Play Store como si fuera un APK. Se pueden aceptar APK directos autorizados o integrar apkeep/Play Developer API solo para artefactos y cuentas con autorización.
