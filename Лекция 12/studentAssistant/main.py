#!/usr/bin/env python3
"""
MCP Server для работы с файлами (Sandboxed & LLM-Optimized)
Зависимости: pip install mcp
"""
import os
import json
import shutil
import re
import logging
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("StudentAssistant")
passMin=50
passGood=70
passPerfect=90

students ={
    "12351261251":{
        "name":"Иванов Иван Иванович",
        "group":"ТРУ-26",
        "grades":{
            "Математика":[5,1,2,6,1,10,4,8],
            "История":[2,1,7,2,5,2,10,2,2,1],
            "Английский":[1,2,7,2,1,5]
        }
    },
    "51351261851":{
        "name":"Петров Петр Петрович",
        "group":"ТРУ-26",
        "grades":{
            "Математика":[9,3,2,6,1,10,4,8],
            "История":[2,1,7,7,5,2,10,2,5,1],
            "Английский":[1,2,1,5]
        }
    }
}

@mcp.tool("getStudentPoints")
def calculate_gpa(student:str, subject:str="")-> str:
    """"
    Инструмент для получения студентом информации о своих баллах по предметам.
    Параметры: номер зачетки студента и предмет, если предмет не указан, то получает информацию по всем.
    """
    if student in students:
        if (subject != ""):
            if(subject in students[student]["grades"]):
                studentResultArr = students[student]["grades"][subject]
                total = str(sum(studentResultArr))
                return "Студент имеет "+ total + " баллов по предмету: "+subject

            else:
                return "У студента нет баллов по данному предмету"
        else:
            allSubjects= students[student]["grades"]
            message=""
            for subject, points in allSubjects.items():
                total = str(sum(points))
                message = message + " сумма баллов по предмету "+ subject +" :"+total
            return  message
    else:
        return "Данного студента нет в нашей базе данных"


@mcp.tool("calculateFinal")
def calculate_final(student:str)-> str:
    """"
    Инструмент для получения студентом информации об итоговом балле по всем своим предметам во время сессии.
    Параметры: номер зачетки студента
    """
    itemsFinal={}
    if student in students:
        allSubjects=students[student]["grades"]
        for subject, points in allSubjects.items():
            itemTotal = sum(points)
            finalResult="Незачет"
            if itemTotal> passPerfect or itemTotal == passPerfect:
                finalResult="Отлично"
            elif itemTotal> passGood or itemTotal == passGood:
                finalResult = "Хорошо"
            elif itemTotal > passMin or itemTotal == passMin:
                finalResult = "Удовлетварительно"
            itemsFinal[subject]=finalResult

        return json.dumps(itemsFinal, ensure_ascii=False, indent=2)
    else:
        return "Данного студента нет в нашей базе данных"


@mcp.tool("calculateNeededPoints")
def calculate_needed_points(student: str, subject: str = "") -> str:
    """
    Инструмент для расчета количества баллов, необходимых студенту
    для получения определенной оценки (Удовлетворительно, Хорошо, Отлично).
    Параметры: номер зачетки студента и предмет. Если предмет не указан, расчет по всем доступным предметам.
    Возвращает ответ в формате JSON.
    """

    # Thresholds
    thresholds = {
        "Удовлетворительно": passMin,
        "Хорошо": passGood,
        "Отлично": passPerfect
    }

    if student not in students:
        return json.dumps({"error": "Студент не найден"}, ensure_ascii=False)

    result = {"student_id": student}

    # Helper to process a subject
    def process_subject(subj_name):
        current_grades = students[student]["grades"].get(subj_name, [])
        current_total = sum(current_grades)

        needed_points = {}
        for grade_name, threshold in thresholds.items():
            if current_total >= threshold:
                needed_points[grade_name] = 0  # Already achieved or more than enough
            else:
                needed_points[grade_name] = threshold - current_total

        return {
            "subject": subj_name,
            "current_score": current_total,
            "needed_to_pass": needed_points["Удовлетворительно"],
            "needed_to_good": needed_points["Хорошо"],
            "needed_to_perfect": needed_points["Отлично"]
        }

    if subject:
        if subject in students[student]["grades"]:
            result["data"] = process_subject(subject)
        else:
            return json.dumps({"error": f"Предмет {subject} не найден у студента"}, ensure_ascii=False)
    else:
        # Calculate for all subjects
        data_list = []
        for subj_name in students[student]["grades"]:
            data_list.append(process_subject(subj_name))
        result["data"] = data_list

    return json.dumps(result, ensure_ascii=False)

if __name__ == "__main__":
    print("Начало сервера")
    mcp.run()