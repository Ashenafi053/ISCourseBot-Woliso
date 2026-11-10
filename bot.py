import asyncio
import http.server
import logging
import os
import socketserver
import threading
from html import escape

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import API_TOKEN, SUPER_ADMIN_ID
from database import (
    init_db, seed_courses, get_courses, get_course,
    get_materials, get_materials_with_ids, get_all_materials_detailed,
    get_exit_materials, add_material, delete_material_db, get_course_by_code,
    get_admin_set, add_admin_db, remove_admin_db, get_admin_stats
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# --- INSTANT PORT BINDING FOR RENDER FREE TIER ---
def run_web_server():
    port = int(os.getenv("PORT", 10000))
    
    class HealthHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"IS Course Bot is active!")
            
        def log_message(self, format, *args):
            pass # Suppress noisy HTTP logs

    try:
        with socketserver.TCPServer(("0.0.0.0", port), HealthHandler) as httpd:
            print(f"Web health-check server running on port {port}")
            httpd.serve_forever()
    except Exception as e:
        print(f"Web server error: {e}")

# Start the web server immediately in a background thread
threading.Thread(target=run_web_server, daemon=True).start()
# ------------------------------------------------

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

MATERIAL_TYPES = {
    "lecture": "Lecture Notes & PPTs",
    "assign": "Assignments & Lab Guides",
    "exam": "Past Exams",
}


def is_admin(user_id: int | None) -> bool:
    if user_id is None:
        return False
    return user_id in get_admin_set()


def home_keyboard(admin: bool = False):
    kb = InlineKeyboardBuilder()
    kb.button(text="🎓 Exit Exam Materials", callback_data="exit_exam_menu")
    kb.button(text="📚 Course Materials", callback_data="years")
    kb.button(text="🏛️ About Information Systems", callback_data="about_is")
    kb.button(text="🧭 Student Success Guide", callback_data="student_guide")
    kb.button(text="❓ Help", callback_data="help")
    if admin:
        kb.button(text="🛡️ Administrator Panel", callback_data="admin_panel")
    kb.adjust(1)
    return kb.as_markup()


def back_keyboard(destination: str, label: str = "⬅️ Back"):
    kb = InlineKeyboardBuilder()
    kb.button(text=label, callback_data=destination)
    return kb.as_markup()


def years_keyboard():
    kb = InlineKeyboardBuilder()
    for year in (2, 3, 4):
        kb.button(text=f"📅 Year {year}", callback_data=f"year:{year}")
    kb.button(text="🏠 Home", callback_data="home")
    kb.adjust(1)
    return kb.as_markup()


def semesters_keyboard(year: int):
    kb = InlineKeyboardBuilder()
    for sem in (1, 2):
        kb.button(text=f"📖 Semester {sem}", callback_data=f"sem:{year}:{sem}")
    kb.button(text="⬅️ Back to Years", callback_data="years")
    kb.adjust(1)
    return kb.as_markup()


def courses_keyboard(courses, year: int, semester: int):
    kb = InlineKeyboardBuilder()
    for course_id, code, title in courses:
        kb.button(text=f"{code}: {title}"[:60], callback_data=f"course:{course_id}")
    if not courses:
        kb.button(text="No courses available yet", callback_data="noop")
    kb.button(text="⬅️ Back to Semesters", callback_data=f"year:{year}")
    kb.adjust(1)
    return kb.as_markup()


def course_keyboard(course_id: int, year: int, semester: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="📄 Lecture Notes & PPTs", callback_data=f"mat:{course_id}:lecture")
    kb.button(text="📝 Assignments & Guides", callback_data=f"mat:{course_id}:assign")
    kb.button(text="📜 Past Exams", callback_data=f"mat:{course_id}:exam")
    kb.button(text="⬅️ Back to Courses", callback_data=f"sem:{year}:{semester}")
    kb.adjust(1)
    return kb.as_markup()


def admin_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="📤 Upload & Command Guide", callback_data="admin_upload_help")
    kb.button(text="📋 List All Materials", callback_data="admin_list_materials")
    kb.button(text="👥 Manage Admins", callback_data="admin_manage_admins")
    kb.button(text="📚 Material Counts", callback_data="admin_stats")
    kb.button(text="🏠 Home", callback_data="home")
    kb.adjust(1)
    return kb.as_markup()


def upload_category_keyboard(course_id: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="📄 Lecture Notes & PPTs", callback_data=f"upl:{course_id}:lecture")
    kb.button(text="📝 Assignments & Guides", callback_data=f"upl:{course_id}:assign")
    kb.button(text="📜 Past Exams", callback_data=f"upl:{course_id}:exam")
    kb.button(text="🎓 Exit Exam Material", callback_data=f"upl:{course_id}:exit")
    kb.adjust(1)
    return kb.as_markup()


async def show_menu(callback: types.CallbackQuery, text: str, markup=None):
    try:
        if callback.message:
            await callback.message.edit_text(text, reply_markup=markup)
    except Exception:
        if callback.message:
            await callback.message.answer(text, reply_markup=markup)


@dp.message(CommandStart())
async def start(message: types.Message):
    name = escape(message.from_user.full_name if message.from_user else "student")
    admin = is_admin(message.from_user.id if message.from_user else None)
    greeting = (
        f"👋 Hello, <b>{name}</b>!\n\n"
        "<b>IS Course Material Bot</b>\n"
        "Ambo University – Woliso Campus\n\n"
        "Your academic companion for course materials and guidance. "
        "Choose an option below to get started."
    )
    await message.answer(greeting, reply_markup=home_keyboard(admin))


@dp.message(Command("help"))
async def help_command(message: types.Message):
    admin = is_admin(message.from_user.id if message.from_user else None)
    text = (
        "📖 <b>How to Interact with IS Course Bot</b>\n\n"
        "1. <b>Main Menu:</b> Use <code>/start</code> anytime to reopen the main navigation panel.\n"
        "2. <b>Browsing Course Materials:</b> Tap <b>📚 Course Materials</b> -> Select Year (2, 3, or 4) -> Select Semester -> Choose Course -> Select material category to receive downloadable files instantly.\n"
        "3. <b>Exit Exam Prep:</b> Tap <b>🎓 Exit Exam Materials</b> for national exam modules, model questions, and preparation guides via <b>About Exit Exam</b>.\n"
        "4. <b>Academic Guidance:</b> Read <b>🏛️ About Information Systems</b> and the <b>🧭 Student Success Guide</b> for tips on programming, databases, and professional development.\n\n"
    )
    if admin:
        text += "🛡️ <b>Administrator Quick Guide:</b>\nSend any document with the course code in the caption, then tap the category button. Use <code>/delete ID</code> to remove materials."
    await message.answer(text, reply_markup=home_keyboard(admin))


@dp.callback_query(F.data == "help")
async def help_callback(callback: types.CallbackQuery):
    admin = is_admin(callback.from_user.id)
    text = (
        "📖 <b>How to Interact with IS Course Bot</b>\n\n"
        "• Access <b>Course Materials</b> by browsing academic year, semester, and course.\n"
        "• Download <b>Exit Exam Materials</b> for national board exam reviews.\n"
        "• Use <code>/start</code> anytime to return to the main menu."
    )
    await show_menu(callback, text, home_keyboard(admin))
    await callback.answer()


@dp.callback_query(F.data == "home")
async def home(callback: types.CallbackQuery):
    admin = is_admin(callback.from_user.id)
    await show_menu(
        callback,
        "👋 <b>IS Course Material Bot</b>\nSelect an option below:",
        home_keyboard(admin),
    )
    await callback.answer()


@dp.callback_query(F.data == "exit_exam_menu")
async def exit_exam_menu(callback: types.CallbackQuery):
    materials = get_exit_materials()
    admin = is_admin(callback.from_user.id if callback.from_user else None)

    kb = InlineKeyboardBuilder()
    kb.button(text="ℹ️ About Exit Exam & Preparation", callback_data="about_exit_exam")
    kb.button(text="🏠 Main Menu", callback_data="home")
    kb.adjust(1)

    if not materials:
        text = (
            "🎓 <b>Information Systems Exit Exam Materials</b>\n"
            "<i>Ambo University – Woliso Campus</i>\n\n"
            "Comprehensive national exit exam guidelines, review modules, and model questions.\n\n"
            "⚠️ <i>No exit exam materials have been uploaded yet. Please check back soon!</i>"
        )
        await show_menu(callback, text, kb.as_markup())
        await callback.answer()
        return

    await callback.answer(f"Sending {len(materials)} exit exam file(s)…")
    await show_menu(
        callback,
        "🎓 <b>Information Systems Exit Exam Materials</b>\n\n"
        "Here are the available exit exam documents:",
        kb.as_markup()
    )
    
    for mat_id, title, file_id in materials:
        if admin:
            caption = (
                f"🎓 <b>Exit Exam — {escape(title)}</b>\n"
                f"🆔 <i>Material ID: {mat_id}</i>\n"
                f"🗑️ <i>Delete: <code>/delete {mat_id}</code></i>"
            )
        else:
            caption = (
                f"🎓 <b>Exit Exam — {escape(title)}</b>\n"
                "<i>IS Course Material Bot</i>"
            )
        try:
            await callback.message.answer_document(document=file_id, caption=caption)
        except Exception:
            logger.exception("Could not send exit exam material")

    await callback.message.answer(
        "📂 All exit exam files delivered successfully.",
        reply_markup=home_keyboard(admin)
    )


@dp.callback_query(F.data == "about_exit_exam")
async def about_exit_exam(callback: types.CallbackQuery):
    text = (
        "🇪🇹 <b>ETHIOPIAN NATIONAL EXIT EXAMINATION</b>\n"
        "<b>BSc Information Systems: Competency Framework & Preparation Guide</b>\n"
        "<i>Ministry of Education Framework (Prepared: August 2022)</i>\n\n"
        
        "📌 <b>1. Overview & Framework Purpose</b>\n"
        "The national Exit Exam assesses IS graduates across core professional competencies. "
        "Out of 56 courses (256 ECTS) in the 4-year degree program, <b>15 Core Courses (83 ECTS / 49 Credit Hours)</b> "
        "were selected and grouped into <b>5 Major Themes</b>.\n\n"

        "📚 <b>2. The Five Examination Themes & Core Courses</b>\n\n"
        "💻 <b>THEME 1: Computer Programming & Web Technology</b>\n"
        "• <i>Courses:</i> Basic Computer Programming I, OOP, Internet Programming, Multimedia IS.\n"
        "• <i>Focus:</i> Variables, loops, functions, OOP (classes, inheritance, encapsulation, polymorphism), client-server web apps, dynamic web development.\n\n"

        "🌐 <b>THEME 2: Networking & Information Security</b>\n"
        "• <i>Courses:</i> Data Communication & Computer Networks, Information System Security.\n"
        "• <i>Focus:</i> OSI & TCP/IP models, IPv4/IPv6 subnetting, routing, cryptography, authentication, threat detection.\n\n"

        "🗄️ <b>THEME 3: Data & Information Management</b>\n"
        "• <i>Courses:</i> Database Systems, Information Storage & Retrieval.\n"
        "• <i>Focus:</i> ER Diagrams, SQL, 1NF–3NF Normalization, ACID transactions, search indexing & retrieval algorithms.\n\n"

        "🤖 <b>THEME 4: Intelligent Systems</b>\n"
        "• <i>Courses:</i> Fundamentals of AI, Knowledge Management, Intro to Machine Learning.\n"
        "• <i>Focus:</i> Intelligent agents, search algorithms, expert systems, supervised/unsupervised ML, regression, classification & model evaluation.\n\n"

        "⚙️ <b>THEME 5: IS Development & Management</b>\n"
        "• <i>Courses:</i> Systems Analysis & Design, Management of IS & Services, IS Project Management, Enterprise Systems.\n"
        "• <i>Focus:</i> SDLC, UML modeling, Management Information Systems (MIS), IT governance, WBS, Agile/Scrum, ERP integration."
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="➡️ Next: Themes 4-5 & Prep Strategy", callback_data="exit_exam_part2")
    kb.button(text="🎓 Back to Exit Exam Menu", callback_data="exit_exam_menu")
    kb.button(text="🏠 Main Menu", callback_data="home")
    kb.adjust(1)
    await show_menu(callback, text, kb.as_markup())
    await callback.answer()


@dp.callback_query(F.data == "exit_exam_part2")
async def exit_exam_part2(callback: types.CallbackQuery):
    text = (
        "🎯 <b>3. Recommended Preparation Strategy</b>\n"
        "1. <b>Study Systematically:</b> Master all 15 core courses organized by their respective themes.\n"
        "2. <b>Theory + Practical:</b> Do not rely on memorization—practice analyzing code, writing SQL, designing ERD/UML diagrams, and solving scenarios.\n"
        "3. <b>Targeted Revision & Mock Exams:</b> Identify weak themes and test yourself under timed conditions.\n\n"
        "<i>Primary Reference: Ministry of Education, Competency Focus Areas for BSc in Information Systems.</i>"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Back to Part 1", callback_data="about_exit_exam")
    kb.button(text="🎓 Back to Exit Exam Menu", callback_data="exit_exam_menu")
    kb.button(text="🏠 Main Menu", callback_data="home")
    kb.adjust(1)
    await show_menu(callback, text, kb.as_markup())
    await callback.answer()


@dp.callback_query(F.data == "about_is")
async def about_is(callback: types.CallbackQuery):
    admin = is_admin(callback.from_user.id if callback.from_user else None)
    text = (
        "🏛️ <b>About Information Systems</b>\n"
        "<i>Ambo University – Woliso Campus</i>\n\n"
        "<b>What is Information Systems?</b>\n"
        "Information Systems (IS) connects people, business processes, data, "
        "and technology to help organizations operate effectively and make better decisions.\n\n"
        "<b>Career Directions:</b>\n"
        "Systems analyst, software developer, database specialist, business intelligence analyst, and IT consultant."
    )
    await show_menu(callback, text, back_keyboard("home", "🏠 Main Menu"))
    await callback.answer()


@dp.callback_query(F.data == "student_guide")
async def student_guide(callback: types.CallbackQuery):
    admin = is_admin(callback.from_user.id if callback.from_user else None)
    text = (
        "🧭 <b>Student Success Guide</b>\n\n"
        "• <b>Practise code regularly:</b> write programs and solve exercises weekly.\n"
        "• <b>Master databases:</b> understand tables, primary/foreign keys, and SQL.\n"
        "• <b>Build real projects:</b> create a portfolio of finished applications.\n"
        "• <b>Use version control:</b> learn Git and maintain clean code repositories."
    )
    await show_menu(callback, text, back_keyboard("home", "🏠 Main Menu"))
    await callback.answer()


@dp.callback_query(F.data == "years")
async def years(callback: types.CallbackQuery):
    await show_menu(callback, "📂 <b>Select your academic year:</b>", years_keyboard())
    await callback.answer()


@dp.callback_query(F.data.startswith("year:"))
async def select_year(callback: types.CallbackQuery):
    try:
        year = int(callback.data.split(":")[1])
        if year not in (2, 3, 4):
            raise ValueError
    except (ValueError, IndexError):
        await callback.answer("Invalid year selection.", show_alert=True)
        return
    await show_menu(callback, f"📅 <b>Year {year}</b>\nChoose a semester:", semesters_keyboard(year))
    await callback.answer()


@dp.callback_query(F.data.startswith("sem:"))
async def select_semester(callback: types.CallbackQuery):
    try:
        _, y, s = callback.data.split(":")
        year, semester = int(y), int(s)
        if year not in (2, 3, 4) or semester not in (1, 2):
            raise ValueError
    except ValueError:
        await callback.answer("Invalid semester selection.", show_alert=True)
        return
    courses = get_courses(year, semester)
    await show_menu(
        callback,
        f"📚 <b>Year {year} — Semester {semester}</b>\nChoose a course:",
        courses_keyboard(courses, year, semester),
    )
    await callback.answer()


@dp.callback_query(F.data == "noop")
async def noop(callback: types.CallbackQuery):
    await callback.answer("No courses are available in this section yet.")


@dp.callback_query(F.data.startswith("course:"))
async def select_course(callback: types.CallbackQuery):
    try:
        course_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("Invalid course.", show_alert=True)
        return
    course = get_course(course_id)
    if not course:
        await callback.answer("Course not found.", show_alert=True)
        return
    code, title, year, semester = course
    await show_menu(
        callback,
        f"📖 <b>{escape(code)}: {escape(title)}</b>\n\nSelect a material category:",
        course_keyboard(course_id, year, semester),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("mat:"))
async def select_materials(callback: types.CallbackQuery):
    try:
        _, course_id_text, material_type = callback.data.split(":")
        course_id = int(course_id_text)
        if material_type not in MATERIAL_TYPES:
            raise ValueError
    except ValueError:
        await callback.answer("Invalid material category.", show_alert=True)
        return
        
    course = get_course(course_id)
    if not course:
        await callback.answer("Course not found.", show_alert=True)
        return
        
    code, title, year, semester = course
    admin = is_admin(callback.from_user.id if callback.from_user else None)
    
    if admin:
        materials = get_materials_with_ids(course_id, material_type)
    else:
        materials = [(None, t, f) for t, f in get_materials(course_id, material_type)]

    if not materials:
        await show_menu(
            callback,
            f"📂 <b>{escape(code)}: {escape(title)}</b>\n\n"
            f"No {escape(MATERIAL_TYPES[material_type].lower())} have been uploaded yet.",
            back_keyboard(f"course:{course_id}", "⬅️ Back to Course"),
        )
        await callback.answer()
        return

    await callback.answer(f"Sending {len(materials)} file(s)…")
    
    for item in materials:
        if admin:
            mat_id, material_title, file_id = item
            caption = (
                f"📚 <b>{escape(code)} — {escape(material_title)}</b>\n"
                f"🆔 <i>Material ID: {mat_id}</i>\n"
                f"🗑️ <i>Delete: <code>/delete {mat_id}</code></i>"
            )
        else:
            _, material_title, file_id = item
            caption = (
                f"📚 <b>{escape(code)} — {escape(material_title)}</b>\n"
                "<i>IS Course Material Bot</i>"
            )
            
        try:
            await callback.message.answer_document(document=file_id, caption=caption)
        except Exception:
            logger.exception("Could not send material for course %s", course_id)

    await callback.message.answer(
        "📂 All requested course materials delivered.",
        reply_markup=home_keyboard(admin)
    )


@dp.message(Command("delete"))
async def cmd_delete_material(message: types.Message):
    if not message.from_user or not is_admin(message.from_user.id):
        return
        
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.reply("⚠️ Usage: <code>/delete MATERIAL_ID</code>\n(You can see the Material ID under each file when browsing as an admin).")
        return
        
    mat_id = int(parts[1].strip())
    
    try:
        delete_material_db(mat_id)
        await message.reply(f"✅ Successfully deleted material with ID <code>{mat_id}</code>.")
    except Exception:
        logger.exception("Failed to delete material")
        await message.reply("❌ Could not delete the material. Check logs.")


@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied.", show_alert=True)
        return
    await show_menu(
        callback,
        "🛡️ <b>Administrator Panel</b>\n\nManage the course-material library, administrators, and view commands.",
        admin_keyboard(),
    )
    await callback.answer()


@dp.callback_query(F.data == "admin_upload_help")
async def admin_upload_help(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied.", show_alert=True)
        return
    text = (
        "📤 <b>Administrator Upload & Command Reference</b>\n\n"
        "<b>1. How to Upload Materials:</b>\n"
        "• Send any document (PDF, DOCX, PPTX) to this chat in private.\n"
        "• Put **only the course code** in the caption (e.g., <code>InSy2071</code> or <code>EXIT</code>).\n"
        "• Tap the category button that appears to complete the upload.\n\n"
        "<b>2. Complete Admin Commands List:</b>\n"
        "• <code>/delete MATERIAL_ID</code> — Removes a specific file from the database.\n"
        "• <code>/addadmin TELEGRAM_USER_ID</code> — Grants admin rights to another user.\n"
        "• <code>/removeadmin TELEGRAM_USER_ID</code> — Revokes admin rights from a user.\n"
        "• <code>/start</code> — Opens the main student interface.\n"
        "• <code>/help</code> — Displays general bot interaction guides."
    )
    await show_menu(callback, text, back_keyboard("admin_panel", "⬅️ Admin Panel"))
    await callback.answer()


@dp.callback_query(F.data == "admin_list_materials")
async def admin_list_materials(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied.", show_alert=True)
        return
    
    materials = get_all_materials_detailed()
    if not materials:
        await show_menu(
            callback,
            "📋 <b>Material Library</b>\n\nNo materials have been uploaded yet.",
            back_keyboard("admin_panel", "⬅️ Admin Panel")
        )
        await callback.answer()
        return

    header = f"{'ID':<4} | {'Code':<9} | {'Type':<6} | {'Title'}\n"
    separator = "-" * 45 + "\n"
    rows_str = ""
    
    for mat_id, code, m_type, title in materials[:30]:
        short_title = (title[:16] + '..') if len(title) > 18 else title
        rows_str += f"{mat_id:<4} | {code:<9} | {m_type:<6} | {short_title}\n"
    
    table_text = f"<pre>{header}{separator}{rows_str}</pre>"
    if len(materials) > 30:
        table_text += f"\n<i>Showing latest 30 of {len(materials)} files. Use /delete ID to remove.</i>"
    else:
        table_text += f"\n<i>Total files: {len(materials)}. Use /delete ID to remove.</i>"

    await show_menu(
        callback,
        f"📋 <b>Uploaded Materials Inventory</b>\n\n{table_text}",
        back_keyboard("admin_panel", "⬅️ Admin Panel")
    )
    await callback.answer()


@dp.callback_query(F.data == "admin_manage_admins")
async def admin_manage_admins(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied.", show_alert=True)
        return
    
    admins = get_admin_set()
    admin_list_str = "\n".join([f"• <code>{uid}</code>" + (" (Super Admin)" if uid == SUPER_ADMIN_ID else "") for uid in admins])
    
    text = (
        "👥 <b>Administrator Management</b>\n\n"
        f"<b>Current Admins:</b>\n{admin_list_str}\n\n"
        "<b>Commands:</b>\n"
        "• <code>/addadmin TELEGRAM_USER_ID</code>\n"
        "• <code>/removeadmin TELEGRAM_USER_ID</code>"
    )
    await show_menu(callback, text, back_keyboard("admin_panel", "⬅️ Admin Panel"))
    await callback.answer()


@dp.message(Command("addadmin"))
async def cmd_add_admin(message: types.Message):
    if not message.from_user or not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.reply("⚠️ Usage: <code>/addadmin TELEGRAM_USER_ID</code>")
        return
    new_admin_id = int(parts[1].strip())
    try:
        add_admin_db(new_admin_id)
        await message.reply(f"✅ Successfully added user <code>{new_admin_id}</code> as an administrator.")
    except Exception:
        logger.exception("Failed to add admin")
        await message.reply("❌ Could not add admin.")


@dp.message(Command("removeadmin"))
async def cmd_remove_admin(message: types.Message):
    if not message.from_user or not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.reply("⚠️ Usage: <code>/removeadmin TELEGRAM_USER_ID</code>")
        return
    target_id = int(parts[1].strip())

    if SUPER_ADMIN_ID and target_id == SUPER_ADMIN_ID:
        await message.reply("❌ <b>Access Denied:</b> You cannot remove the primary Super Admin!")
        return

    admins = get_admin_set()
    if target_id not in admins:
        await message.reply(f"⚠️ User <code>{target_id}</code> is not an administrator.")
        return

    if len(admins) <= 1:
        await message.reply("⚠️ Cannot remove the last remaining administrator.")
        return

    try:
        remove_admin_db(target_id)
        await message.reply(f"✅ Successfully removed user <code>{target_id}</code> from administrators.")
    except Exception:
        logger.exception("Failed to remove admin")
        await message.reply("❌ Could not remove admin.")


@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied.", show_alert=True)
        return
    courses_count, materials_count, admins_count = get_admin_stats()
    text = (
        "📊 <b>Library Overview</b>\n\n"
        f"Active Courses: <b>{courses_count}</b>\n"
        f"Uploaded materials: <b>{materials_count}</b>\n"
        f"Total Administrators: <b>{admins_count}</b>"
    )
    await show_menu(callback, text, back_keyboard("admin_panel", "⬅️ Admin Panel"))
    await callback.answer()


@dp.message(F.document)
async def handle_upload_document(message: types.Message):
    if not message.from_user or not is_admin(message.from_user.id):
        return
    if message.chat.type != "private":
        await message.reply("Please send course materials to the bot in a private chat.")
        return

    course_code = (message.caption or "").strip()
    if not course_code:
        await message.reply(
            "⚠️ Please include the **Course Code** in the file caption (e.g., <code>InSy2071</code> or <code>EXIT</code>)."
        )
        return

    course = get_course_by_code(course_code)
    if not course:
        await message.reply(f"❌ Course code <code>{escape(course_code)}</code> was not found in the database.")
        return

    course_id, code, title, year, semester = course
    await message.reply(
        f"📁 File received for: <b>{escape(title)}</b> ({escape(code)})\n\n"
        "<b>Select the category for this material:</b>",
        reply_markup=upload_category_keyboard(course_id)
    )


@dp.callback_query(F.data.startswith("upl:"))
async def process_upload_category(callback: types.CallbackQuery):
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Access denied.", show_alert=True)
        return

    try:
        _, course_id_str, material_type = callback.data.split(":")
        course_id = int(course_id_str)
    except (ValueError, IndexError):
        await callback.answer("Invalid selection.", show_alert=True)
        return

    message = callback.message
    if not message or not message.reply_to_message or not message.reply_to_message.document:
        await callback.answer("Original document not found. Please try uploading again.", show_alert=True)
        return

    doc = message.reply_to_message.document
    file_id = doc.file_id
    file_title = doc.file_name or "Course Document"

    course = get_course(course_id)
    if not course:
        await callback.answer("Course not found.", show_alert=True)
        return

    code, title, year, semester = course

    try:
        add_material(course_id, material_type, file_title, file_id)
    except Exception:
        logger.exception("Failed to save uploaded material")
        await callback.answer("❌ Failed to save material to database.", show_alert=True)
        return

    category_name = MATERIAL_TYPES.get(material_type, "Exit Exam Material")
    
    await callback.answer("Successfully uploaded!")
    try:
        await message.edit_text(
            f"✅ <b>Material Uploaded Successfully!</b>\n\n"
            f"📚 Course: <code>{escape(code)} — {escape(title)}</code>\n"
            f"📂 Category: <b>{escape(category_name)}</b>\n"
            f"📄 File: <i>{escape(file_title)}</i>"
        )
    except Exception:
        await message.answer(
            f"✅ <b>Material Uploaded Successfully!</b>\n\n"
            f"📚 Course: <code>{escape(code)} — {escape(title)}</code>\n"
            f"📂 Category: <b>{escape(category_name)}</b>"
        )


async def main():
    init_db()
    seed_courses()
    logger.info("IS Course Material Bot is starting")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())