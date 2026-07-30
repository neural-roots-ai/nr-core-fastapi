"""Learning-page/program-catalog read APIs backed by NRDB tables.

Ported from a sync (Session/db.query) implementation in a different repo -
rewritten against this service's async SQLAlchemy 2.0 engine (AsyncSession +
select()), since the sync ORM API used by the original code cannot run on an
async connection.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.catalog import Country, Program, ProgramCategory, ProgramFee, ProgramType
from app.db.models.programs import FAQ, Curriculum, ImageMapping, Mentor, Project, ProgramMapping, Review, Topic


def _review_out(row: Review) -> dict:
    return {
        "review_id": row.review_id,
        "review_sequence": row.review_sequence,
        "reviewer_name": row.reviewer_name,
        "review_desc": row.review_desc,
        "review_type": row.review_type,
        "program_type": row.program_type,
        "is_active": row.is_active,
    }


def _faq_out(row: FAQ) -> dict:
    return {
        "faq_id": row.faq_id,
        "faq_sequence": row.faq_sequence,
        "faq_type": row.faq_type,
        "faq_question": row.faq_question,
        "faq_answer": row.faq_answer,
        "is_active": row.is_active,
    }


def _project_out(row: Project) -> dict:
    return {
        "project_id": row.project_id,
        "program_id": row.program_id,
        "project_title": row.project_title,
        "project_description": row.project_description,
        "project_outcome": row.project_outcome,
        "project_sequence": row.project_sequence,
        "project_img": row.project_img,
        "project_tag": row.project_tag,
        "is_active": row.is_active,
    }


async def get_program_details(db: AsyncSession, program_id: int, country: str) -> dict:
    country_id = await _get_active_country_id(db, country)
    if country_id is None:
        raise NotFoundError("Program not found.")

    stmt = (
        select(Program, ProgramCategory, ProgramType, ProgramFee)
        .join(ProgramCategory, Program.program_category_id == ProgramCategory.program_category_id)
        .join(ProgramType, Program.program_type_id == ProgramType.program_type_id)
        .join(ProgramFee, Program.program_id == ProgramFee.program_id)
        .where(
            Program.is_active.is_(True),
            ProgramType.is_active.is_(True),
            ProgramCategory.is_active.is_(True),
            ProgramFee.is_active.is_(True),
            Program.program_id == program_id,
            ProgramFee.country_id == country_id,
        )
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        raise NotFoundError("Program not found.")
    program, program_category, program_type, program_fee = row

    curriculum = (
        await db.execute(
            select(Curriculum).where(Curriculum.program_id == program_id, Curriculum.is_active.is_(True))
        )
    ).scalars().all()

    faq = (
        await db.execute(
            select(FAQ).where(
                FAQ.faq_type.in_(["General", program_type.program_type]),
                FAQ.is_active.is_(True),
            )
        )
    ).scalars().all()

    program_review = (
        await db.execute(
            select(Review).where(
                Review.program_type == program_type.program_type_id,
                Review.review_type == program_category.program_category,
                Review.is_active.is_(True),
            )
        )
    ).scalars().all()

    program_project = (
        await db.execute(select(Project).where(Project.program_id == program_id, Project.is_active.is_(True)))
    ).scalars().all()

    return {
        "program_id": program.program_id,
        "program_name": program.program_name,
        "program_sequence": program.program_sequence,
        "tag": program.tag,
        "program_img": program.program_img,
        "program_category": program_category.program_category,
        "program_type": program_type.program_type,
        "program_duration": program.program_duration,
        "program_desc": program.program_desc,
        "program_start_date": program.program_start_date,
        "program_fee": program_fee.program_fee,
        "discount": program_fee.discount,
        "payment_link": program_fee.payment_link,
        "country": country,
        "curriculum": [
            {
                "curriculum_id": c.curriculum_id,
                "program_id": c.program_id,
                "module_id": c.module_id,
                "curriculum_title": c.curriculum_title,
                "topics": c.topics,
                "module_duration": c.module_duration,
                "is_active": c.is_active,
            }
            for c in curriculum
        ],
        "faq": [_faq_out(f) for f in faq],
        "program_review": [_review_out(r) for r in program_review],
        "program_project": [_project_out(p) for p in program_project],
    }


async def _get_active_country_id(db: AsyncSession, country: str) -> int | None:
    return (
        await db.execute(select(Country.country_id).where(Country.country == country, Country.is_active.is_(True)))
    ).scalar_one_or_none()


def _program_list_item(program_data: Program, program_fee_data: ProgramFee, category_label: str, country: str) -> dict:
    return {
        "program_id": program_data.program_id,
        "program_name": program_data.program_name,
        "program_sequence": program_data.program_sequence,
        "tag": program_data.tag,
        "program_img": program_data.program_img,
        "program_desc": program_data.program_desc,
        "program_category": category_label,
        "program_duration": program_data.program_duration,
        "program_start_date": program_data.program_start_date,
        "program_fee": program_fee_data.program_fee,
        "discount": program_fee_data.discount,
        "payment_link": program_fee_data.payment_link,
        "country": country,
    }


async def get_program_list_by_category(db: AsyncSession, country: str) -> dict:
    country_id = await _get_active_country_id(db, country)
    if country_id is None:
        return {}

    stmt = (
        select(Program, ProgramCategory, ProgramFee)
        .join(ProgramCategory, Program.program_category_id == ProgramCategory.program_category_id)
        .join(ProgramFee, Program.program_id == ProgramFee.program_id)
        .where(
            Program.is_active.is_(True),
            ProgramCategory.is_active.is_(True),
            ProgramFee.is_active.is_(True),
            ProgramFee.country_id == country_id,
        )
        .order_by(Program.program_sequence)
    )
    rows = (await db.execute(stmt)).all()

    response: dict[str, list[dict]] = {}
    for program_data, program_category_data, program_fee_data in rows:
        response.setdefault(program_category_data.program_category, []).append(
            _program_list_item(program_data, program_fee_data, program_category_data.program_category, country)
        )
    return response


async def get_program_list_by_type(db: AsyncSession, country: str) -> dict:
    country_id = await _get_active_country_id(db, country)
    if country_id is None:
        return {}

    stmt = (
        select(Program, ProgramType, ProgramFee)
        .join(ProgramType, Program.program_type_id == ProgramType.program_type_id)
        .join(ProgramFee, Program.program_id == ProgramFee.program_id)
        .where(
            Program.is_active.is_(True),
            ProgramType.is_active.is_(True),
            ProgramFee.is_active.is_(True),
            ProgramFee.country_id == country_id,
        )
        .order_by(Program.program_sequence)
    )
    rows = (await db.execute(stmt)).all()

    response: dict[str, list[dict]] = {}
    for program_data, program_type_data, program_fee_data in rows:
        response.setdefault(program_type_data.program_type, []).append(
            _program_list_item(program_data, program_fee_data, program_type_data.program_type, country)
        )
    return response


async def get_learning_page_review_list(db: AsyncSession) -> list[dict]:
    rows = (
        await db.execute(
            select(Review)
            .where(Review.is_active.is_(True), Review.review_type.in_(["Guided Project"]))
            .order_by(Review.review_sequence)
        )
    ).scalars().all()
    return [_review_out(r) for r in rows]


async def get_learning_page_faq(db: AsyncSession) -> list[dict]:
    rows = (
        await db.execute(
            select(FAQ).where(FAQ.is_active.is_(True), FAQ.faq_type == "General").order_by(FAQ.faq_sequence)
        )
    ).scalars().all()
    return [_faq_out(f) for f in rows]


async def get_curriculum_by_program_id(db: AsyncSession, program_id: int) -> dict:
    stmt = (
        select(Curriculum, Topic)
        .join(Topic, Curriculum.curriculum_id == Topic.curriculum_id)
        .where(
            Curriculum.is_active.is_(True),
            Topic.is_active.is_(True),
            Curriculum.program_id == program_id,
        )
        .order_by(Curriculum.program_id)
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        raise NotFoundError("Curriculum not found.")

    response: dict[str, dict] = {}
    for curriculum_data, topic_data in rows:
        topic_dict = {
            "topic_id": topic_data.topic_id,
            "curriculum_id": topic_data.curriculum_id,
            "topic": topic_data.topic,
            "module_id": topic_data.module_id,
            "is_active": topic_data.is_active,
        }
        if curriculum_data.curriculum_title not in response:
            response[curriculum_data.curriculum_title] = {
                "curriculum_id": curriculum_data.curriculum_id,
                "program_id": curriculum_data.program_id,
                "module_id": curriculum_data.module_id,
                "curriculum_title": curriculum_data.curriculum_title,
                "topic_list": [topic_dict],
                "is_active": curriculum_data.is_active,
            }
        else:
            response[curriculum_data.curriculum_title]["topic_list"].append(topic_dict)
    return response


async def get_project_list(db: AsyncSession) -> list[dict]:
    rows = (
        await db.execute(select(Project).where(Project.is_active.is_(True)).order_by(Project.project_sequence))
    ).scalars().all()
    return [_project_out(p) for p in rows]


async def get_program_review_list(db: AsyncSession) -> list[dict]:
    rows = (
        await db.execute(select(Review).where(Review.is_active.is_(True)).order_by(Review.review_sequence))
    ).scalars().all()
    return [_review_out(r) for r in rows]


async def get_program_mapping_list(db: AsyncSession) -> list[dict]:
    rows = (await db.execute(select(ProgramMapping).where(ProgramMapping.is_active.is_(True)))).scalars().all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "value": row.value,
            "desc": row.desc,
            "is_active": row.is_active,
        }
        for row in rows
    ]


async def get_image_mapping_list(db: AsyncSession) -> list[dict]:
    rows = (await db.execute(select(ImageMapping).where(ImageMapping.is_active.is_(True)))).scalars().all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "img_path": row.img_path,
            "desc": row.desc,
            "is_active": row.is_active,
        }
        for row in rows
    ]


async def get_mentor_list(db: AsyncSession) -> list[dict]:
    rows = (await db.execute(select(Mentor).where(Mentor.is_active.is_(True)))).scalars().all()
    return [
        {
            "mentor_id": row.mentor_id,
            "name": row.name,
            "degree": row.degree,
            "work_exp": row.work_exp,
            "company": row.company,
            "university": row.university,
            "img": row.img,
            "skills": row.skills,
            "created_on": row.created_on,
            "updated_on": row.updated_on,
            "is_active": row.is_active,
        }
        for row in rows
    ]
