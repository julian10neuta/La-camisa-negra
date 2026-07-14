"""restore album and cover_url on songs

Estas dos columnas existieron y se eliminaron en la revisión 42abf61683d0
("remove album and cover_url from songs"), que llegó dentro del commit 48f053f
("starting with routers") sin explicar el motivo. Vuelven a propósito:

  1. El documento de análisis del proyecto las pide: la entidad "Canción" lista
     Álbum y Portada entre sus atributos.
  2. Guardarlas no cuesta ninguna llamada extra: el objeto de Spotify que ya
     recibimos al cachear una canción trae album.name y album.images; hasta ahora
     los tirábamos.
  3. NO guardarlas sí cuesta: GET /tracks?ids= (el lote) devuelve 403 para esta
     app, así que recuperar la carátula después obliga a una llamada por canción.
     Esa ráfaga es la que hizo que Spotify baneara la app (dos veces). Ese dato no
     se conocía cuando se quitaron.

Nullable a propósito: las filas que ya existen se rellenan con un backfill
(scripts/backfill_song_album.py), y una canción sin portada debe poder guardarse
igual — la portada es decoración, no un dato del que dependa nada.

Revision ID: b1c4e7d9f2a3
Revises: 42abf61683d0
Create Date: 2026-07-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c4e7d9f2a3'
down_revision: Union[str, Sequence[str], None] = '42abf61683d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('songs', sa.Column('album', sa.String(), nullable=True))
    op.add_column('songs', sa.Column('cover_url', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('songs', 'cover_url')
    op.drop_column('songs', 'album')
