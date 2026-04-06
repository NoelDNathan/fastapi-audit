


# Hay niveles de ocultación. El máximo nivel es ignore, seguido por hash, seguido por mask, y por último raw, no tiene sentido que si persist es ignore, on default sea raw, puede hacer que on_delete solo se puedan definir estrategias que sean más restrictivas que on persist



# Test audit
# Si el persist y el on_delete son iguales, on_delete no se aplica