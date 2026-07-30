"""Program/learning-page catalog endpoints (NRDB-backed, read-only).

Public on purpose: these are catalog/marketing pages a visitor browses
before signing up (program listings, reviews, FAQs, mentors) - mirrors the
existing public /payments/programs/{id}/fee lookup rather than the
blanket-auth wrapper the original source repo had on every route here.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbSession
from app.services import program_service

router = APIRouter(tags=["programs"])


@router.get("/get-program-detail")
async def get_program_details(program_id: int, country: str, db: DbSession) -> dict:
    return await program_service.get_program_details(db, program_id, country)


@router.get("/get-program-list-by-category")
async def get_program_list_by_category(country: str, db: DbSession) -> dict:
    return await program_service.get_program_list_by_category(db, country)


@router.get("/get-program-list-by-type")
async def get_program_list_by_type(country: str, db: DbSession) -> dict:
    return await program_service.get_program_list_by_type(db, country)


@router.get("/get-learning-page-reviews")
async def get_learning_page_review_list(db: DbSession) -> list[dict]:
    return await program_service.get_learning_page_review_list(db)


@router.get("/get-learning-page-faqs")
async def get_learning_page_faq(db: DbSession) -> list[dict]:
    return await program_service.get_learning_page_faq(db)


@router.get("/get-curriculum-by-program-id")
async def get_curriculum_by_program_id(program_id: int, db: DbSession) -> dict:
    return await program_service.get_curriculum_by_program_id(db, program_id)


@router.get("/get-project-list")
async def get_project_list(db: DbSession) -> list[dict]:
    return await program_service.get_project_list(db)


@router.get("/get-program-reviews-list")
async def get_program_review_list(db: DbSession) -> list[dict]:
    return await program_service.get_program_review_list(db)


@router.get("/get-program-mapping-list")
async def get_program_mapping_list(db: DbSession) -> list[dict]:
    return await program_service.get_program_mapping_list(db)


@router.get("/get-image-mapping-list")
async def get_image_mapping_list(db: DbSession) -> list[dict]:
    return await program_service.get_image_mapping_list(db)


@router.get("/get-mentor-list")
async def get_mentor_list(db: DbSession) -> list[dict]:
    return await program_service.get_mentor_list(db)
