"""Enforce customer isolation even for SQL/ORM writes bypassing model.clean()."""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("logistics", "0001_initial")]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE logistics_package
                ADD CONSTRAINT package_shipment_customer_fk
                FOREIGN KEY (shipment_id, customer_id)
                REFERENCES logistics_shipment (id, customer_id)
                ON UPDATE NO ACTION ON DELETE NO ACTION
                NOT DEFERRABLE;
            """,
            reverse_sql="""
                ALTER TABLE logistics_package
                DROP CONSTRAINT package_shipment_customer_fk;
            """,
        ),
    ]
