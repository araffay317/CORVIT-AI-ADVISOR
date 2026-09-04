"""Dataset structure inspection route for Corvit AI Advisor (Read-Only)."""
from fastapi import APIRouter
from backend.config import settings
from backend.schemas import DatasetInfoResponse, DatasetCategoryItem

router = APIRouter(prefix="/api/v1", tags=["Dataset Metadata"])

# The 8 canonical Corvit dataset categories and their expected filenames
EXPECTED_CATEGORIES = [
    ("courses", "corvit_courses.txt"),
    ("navttc", "corvit_navttc.txt"),
    ("timetable", "corvit_timetable.txt"),
    ("fees", "corvit_paid_courses_fees.txt"),
    ("admission", "corvit_admission_application.txt"),
    ("infrastructure", "corvit_infrastructure.txt"),
    ("faq", "corvit_faq.txt"),
    ("general", "corvit_general.txt")
]


@router.get("/dataset-info", response_model=DatasetInfoResponse)
async def get_dataset_info() -> DatasetInfoResponse:
    """
    Inspect and report the presence of the 8 dataset categories.
    NOTE (Correction 3): This endpoint strictly verifies file presence.
    It does NOT read, load, preprocess, chunk, or embed content.
    """
    base_dataset = settings.dataset_dir
    items = []

    for folder_name, file_name in EXPECTED_CATEGORIES:
        file_path = base_dataset / folder_name / file_name
        items.append(
            DatasetCategoryItem(
                category=folder_name,
                folder=str(folder_name),
                file_name=file_name,
                exists=file_path.is_file()
            )
        )

    detected_count = sum(1 for item in items if item.exists)

    return DatasetInfoResponse(
        dataset_name="Corvit Knowledge Base",
        categories_detected=detected_count,
        categories=items
    )
