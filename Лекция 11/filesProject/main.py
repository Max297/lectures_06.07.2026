"""
Smart File Sorter - Скрипт для автоматической сортировки файлов и архивов.

Этот скрипт мониторит папку 'files' внутри директории проекта, 
сортирует файлы по расширениям в соответствующие подпапки, 
распаковывает архивы и переименовывает файлы согласно заданному формату.
"""

import os
import shutil
import zipfile
import tarfile
import time  # Добавлен импорт для sleep
from pathlib import Path
from datetime import datetime


class FileSorter:
    """Класс для управления мониторингом и сортировкой файлов."""

    def __init__(self, root_dir: str):
        """
        Инициализация класса.

        Args:
            root_dir (str): Путь к корневой директории проекта.
        """
        self.root_dir = Path(root_dir)
        # Папка, которую будем мониторить
        self.watch_dir = self.root_dir / "files"
        
        # Маппинг расширений на папки для сортировки
        # Добавлена категория Programming_files с расширениями для программирования
        # .ipynb перенесён из documents в Programming_files
        self.extensions_map = {
            'images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg'],
            'documents': ['.pdf', '.doc', '.docx', '.txt', '.rtf'],  # Убран .ipynb
            'Programming_files': [
                '.py', '.ipynb', '.js', '.html', '.css', 
                '.java', '.cpp', '.c', '.h', '.cs', '.php', 
                '.rb', '.go', '.rs', '.swift', '.kt', '.ts', 
                '.jsx', '.tsx', '.vue', '.svelte'
            ],
            'archives': ['.zip', '.rar', '.7z', '.tar', '.gz'],
            'videos': ['.mp4', '.avi', '.mkv', '.mov'],
            'audio': ['.mp3', '.wav', '.flac']
        }

        # Папка для временных файлов (распаковка)
        self.temp_dir = self.root_dir / "_temp_unpack"

    def run(self):
        """Запуск цикла мониторинга."""
        print(f"Запуск монитора папки: {self.watch_dir}")
        
        # Создаем папку для отслеживания, если её нет
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        # Создаем временную папку, если её нет
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        processed_files = set()  # Хранилище обработанных файлов (для предотвращения зацикливания)

        # Проверка и исправление существующих файлов при запуске
        print("\n--- Проверка существующих файлов ---")
        self._fix_existing_files()
        print("--- Проверка завершена ---\n")

        while True:
            try:
                current_files = [f for f in self.watch_dir.iterdir() if f.is_file()]
                
                for file_path in current_files:
                    # Пропускаем временные файлы и уже обработанные
                    if str(file_path) in processed_files or file_path.name.startswith('_'):
                        continue

                    print(f"Обнаружен новый файл: {file_path.name}")
                    
                    # Обработка файла
                    self._process_file(file_path, is_root=True)
                    
                    # Добавляем в список обработанных (используем абсолютный путь для надежности)
                    processed_files.add(str(file_path.resolve()))

            except Exception as e:
                print(f"Ошибка при сканировании папки: {e}")

            time.sleep(2)  # Пауза между проверками

    def _fix_existing_files(self):
        """
        Проверяет все файлы в подпапках и перемещает их в правильные категории.
        
        Этот метод вызывается при запуске скрипта для исправления файлов,
        которые могли оказаться не в той папке после изменения категорий.
        """
        print("Проверка существующих файлов...")
        
        # Проходим по всем подпапкам внутри watch_dir
        for subfolder in self.watch_dir.iterdir():
            if not subfolder.is_dir():
                continue
                
            current_folder_name = subfolder.name
            
            # Проходим по всем файлам в текущей подпапке
            for file_path in subfolder.iterdir():
                if not file_path.is_file():
                    continue
                    
                ext = file_path.suffix.lower()
                
                # Определяем правильную папку для этого файла
                correct_folder_name = None
                for folder, extensions in self.extensions_map.items():
                    if ext in extensions:
                        correct_folder_name = folder
                        break
                
                # Если расширение не найдено в маппинге, используем other_files
                if not correct_folder_name:
                    print(f"Неизвестное расширение {ext} для файла {file_path.name}. Перемещение в 'other_files'.")
                    correct_folder_name = "other_files"
                
                # Если файл уже в правильной папке - пропускаем
                if current_folder_name == correct_folder_name:
                    continue
                
                print(f"Файл {file_path.name} находится не в той категории.")
                print(f"  Текущая папка: {current_folder_name}")
                print(f"  Правильная папка: {correct_folder_name}")
                
                # Перемещаем файл в правильную папку
                target_dir = self.watch_dir / correct_folder_name
                target_dir.mkdir(parents=True, exist_ok=True)
                
                dest_path = target_dir / file_path.name
                
                try:
                    shutil.move(str(file_path), str(dest_path))
                    print(f"  -> Перемещен в {correct_folder_name}/{dest_path.name}")
                except Exception as e:
                    print(f"  -> Ошибка при перемещении: {e}")

    def _process_file(self, file_path: Path, is_root: bool = False):
        """
        Основная логика обработки файла. Определяет тип и вызывает соответствующую функцию.

        Args:
            file_path (Path): Путь к файлу.
            is_root (bool): Флаг, является ли файл корневым (для формирования имени).
        """
        if not file_path.exists():
            return

        # Проверка на архив
        if self._is_archive(file_path):
            print(f"Обнаружен архив: {file_path.name}. Распаковка...")
            archive_name = file_path.stem  # Имя без расширения
            
            try:
                # Создаем временную папку для распаковки с уникальным именем, чтобы не было конфликтов
                temp_extract_dir = self.temp_dir / f"extract_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                temp_extract_dir.mkdir(parents=True, exist_ok=True)

                if file_path.suffix.lower() == '.zip':
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        zip_ref.extractall(temp_extract_dir)
                elif file_path.suffix.lower() in ['.tar', '.gz', '.tgz']:
                    with tarfile.open(file_path, 'r:*') as tar_ref:
                        tar_ref.extractall(temp_extract_dir)
                
                # Удаляем исходный архив после успешной распаковки
                file_path.unlink()

                # Рекурсивно обрабатываем содержимое временной папки
                for item in temp_extract_dir.iterdir():
                    if item.is_file():
                        self._sort_single_file(item, archive_name=archive_name)
                    elif item.is_dir():
                        # Если внутри архива были подпапки, можно рекурсивно вызвать обработку (упрощенно пока только файлы)
                        for sub_item in item.iterdir():
                            if sub_item.is_file():
                                self._sort_single_file(sub_item, archive_name=archive_name)

                # Очистка временной папки
                shutil.rmtree(temp_extract_dir)

            except Exception as e:
                print(f"Ошибка при распаковке архива {file_path.name}: {e}")
        else:
            # Обычный файл
            self._sort_single_file(file_path, archive_name=None)

    def _is_archive(self, file_path: Path) -> bool:
        """
        Проверяет, является ли файл архивом.

        Args:
            file_path (Path): Путь к файлу.

        Returns:
            bool: True если файл является архивом.
        """
        archive_extensions = ['.zip', '.rar', '.7z', '.tar', '.gz', '.tgz']
        return file_path.suffix.lower() in archive_extensions

    def _sort_single_file(self, file_path: Path, archive_name: str = None):
        """
        Перемещает файл в соответствующую папку и переименовывает его.

        Args:
            file_path (Path): Путь к файлу.
            archive_name (str, optional): Имя архива, если файл был внутри него.
        """
        if not file_path.exists():
            return

        ext = file_path.suffix.lower()
        
        # Поиск целевой папки по расширению
        target_folder_name = None
        for folder, extensions in self.extensions_map.items():
            if ext in extensions:
                target_folder_name = folder
                break
        
        # Если расширение не найдено в маппинге, создаем папку "other_files"
        if not target_folder_name:
            print(f"Неизвестное расширение {ext}. Перемещение в папку 'other_files'.")
            target_folder_name = "other_files"

        # Формирование нового имени файла
        original_name = file_path.stem
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        if archive_name:
            new_filename = f"{archive_name}_{original_name}_{date_str}{ext}"
        else:
            new_filename = f"{original_name}_{date_str}{ext}"

        # Создание целевой директории внутри папки 'files'
        target_dir = self.watch_dir / target_folder_name
        target_dir.mkdir(parents=True, exist_ok=True)

        # Полный путь назначения
        dest_path = target_dir / new_filename
        
        # Если файл с таким именем уже существует, добавляем уникальный суффикс (простая защита от коллизий)
        if dest_path.exists():
            unique_id = datetime.now().strftime("%H%M%S")
            dest_path = target_dir / f"{new_filename[:-len(ext)]}_{unique_id}{ext}"

        # Перемещение файла
        try:
            shutil.move(str(file_path), str(dest_path))
            print(f"Файл {file_path.name} перемещен в {target_folder_name}/{dest_path.name}")
        except Exception as e:
            print(f"Ошибка при перемещении файла {file_path.name}: {e}")


if __name__ == "__main__":
    # Путь к корневой папке проекта (автоматически определяется относительно скрипта)
    project_root = Path(__file__).parent
    
    sorter = FileSorter(str(project_root))
    
    try:
        sorter.run()
    except KeyboardInterrupt:
        print("\nМониторинг остановлен пользователем.")
