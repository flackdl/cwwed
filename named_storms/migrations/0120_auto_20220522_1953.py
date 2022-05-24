from django.db import migrations
from psqlextra.backend.migrations.operations import PostgresAddListPartition


class Migration(migrations.Migration):
    dependencies = [
        ('named_storms', '0119_auto_20220522_1951'),
    ]
    operations = [
        PostgresAddListPartition(
           model_name="NsemPsaDataPartition",
           name="florence",
           values=["Florence"],
        ),
        PostgresAddListPartition(
            model_name="NsemPsaDataPartition",
            name="sandy",
            values=["Sandy"],
        ),
        PostgresAddListPartition(
            model_name="NsemPsaDataPartition",
            name="ida",
            values=["Ida"],
        ),
    ]
