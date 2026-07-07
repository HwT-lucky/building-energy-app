"""Report generation endpoints."""
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from models.requests import ReportRequest
from services.report_service import generate_word_report
from tasks.report_task import start_report_task, get_task_status
from config import REPORT_DIR

router = APIRouter()


@router.post("/report")
async def generate_report(req: ReportRequest):
    """Generate and download a Word (.docx) energy analysis report."""
    try:
        data = {
            'building_info': req.building_info,
            'energy_proportion': req.energy_proportion,
            'monthly_trend': req.monthly_trend,
            'carbon_emission': req.carbon_emission,
            'standard_comparison': req.standard_comparison,
            'coal_per_m2_kgce': req.coal_per_m2_kgce,
            'carbon_intensity_kgco2_per_m2': req.carbon_intensity_kgco2_per_m2,
            'data_notes': req.data_notes,
        }
        output_path, output_filename = generate_word_report(data)

        building_name = req.building_info.get('name', '建筑')
        safe_name = building_name.replace('/', '_').replace('\\', '_')

        return FileResponse(
            path=output_path,
            media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            filename=f'{safe_name}_能耗分析报告.docx',
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"报告生成失败: {str(e)}")


@router.post("/report/async")
async def generate_report_async(req: ReportRequest):
    """Start async report generation, return task_id for polling."""
    try:
        data = {
            'building_info': req.building_info,
            'energy_proportion': req.energy_proportion,
            'monthly_trend': req.monthly_trend,
            'carbon_emission': req.carbon_emission,
            'standard_comparison': req.standard_comparison,
            'coal_per_m2_kgce': req.coal_per_m2_kgce,
            'carbon_intensity_kgco2_per_m2': req.carbon_intensity_kgco2_per_m2,
            'data_notes': req.data_notes,
        }
        task_id = start_report_task(data)
        return {"task_id": task_id, "status": "processing"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动报告生成失败: {str(e)}")


@router.get("/report/status/{task_id}")
async def report_status(task_id: str):
    """Poll async report generation status."""
    status = get_task_status(task_id)
    if status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return status


@router.get("/report/download/{filename}")
async def download_report(filename: str):
    """Download a previously generated report."""
    filepath = os.path.join(REPORT_DIR, filename)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="报告文件不存在或已过期")
    return FileResponse(
        path=filepath,
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        filename=filename,
    )
