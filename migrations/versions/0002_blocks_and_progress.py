"""Thêm bảng blocks, ingest_progress và các cột theo dõi quá trình parse

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("parsed_key", sa.String(512)))
    op.add_column("documents", sa.Column("ocr_page_count", sa.Integer))
    op.add_column("documents", sa.Column("parse_seconds", sa.Integer))
    op.add_column(
        "documents",
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "blocks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer,
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page", sa.Integer, nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("block_type", sa.String(16), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("heading_path", sa.Text),
        sa.Column("bbox", JSONB),
        sa.Column("from_ocr", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("document_id", "position", name="blocks_document_position_key"),
    )
    op.create_index("blocks_document_id_idx", "blocks", ["document_id"])
    op.create_index("blocks_document_page_idx", "blocks", ["document_id", "page"])

    op.create_table(
        "ingest_progress",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer,
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page", sa.Integer, nullable=False),
        sa.Column("stage", sa.String(16), nullable=False),
        sa.Column("used_ocr", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("error", sa.Text),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("document_id", "page", name="ingest_progress_doc_page_key"),
    )


def downgrade() -> None:
    op.drop_table("ingest_progress")
    op.drop_index("blocks_document_page_idx", table_name="blocks")
    op.drop_index("blocks_document_id_idx", table_name="blocks")
    op.drop_table("blocks")
    op.drop_column("documents", "updated_at")
    op.drop_column("documents", "parse_seconds")
    op.drop_column("documents", "ocr_page_count")
    op.drop_column("documents", "parsed_key")
