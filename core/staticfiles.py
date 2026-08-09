from django.contrib.staticfiles.storage import ManifestStaticFilesStorage


class LenientManifestStaticFilesStorage(ManifestStaticFilesStorage):
    """Манифест-хэширование, не падающее на битых url() в стороннем CSS.

    Оригинальный ManifestStaticFilesStorage роняет collectstatic целиком,
    если какой-нибудь вбандленный CSS (leaflet и т.п.) ссылается на файл,
    которого нет в сборке. Прод-контейнер запускает collectstatic в CMD,
    так что падение = сломанный деплой. Битую ссылку оставляем как есть.
    """

    manifest_strict = False

    def hashed_name(self, name, content=None, filename=None):
        try:
            return super().hashed_name(name, content, filename)
        except ValueError:
            return name
