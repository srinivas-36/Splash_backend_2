from google import genai
from google.genai import types
from .models import Collection, ProductImage  # ✅ ensure ProductImage is imported
import io
import cloudinary.uploader
import traceback
import base64
from .models import Project, Collection, CollectionItem
from django.shortcuts import render, redirect
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
import os
import requests
import json
from django.conf import settings
import ast
import re
from datetime import timezone
from .models import Project, Collection, CollectionItem, GeneratedImage
from .utils import request_suggestions
from mongoengine.errors import DoesNotExist
from rest_framework.response import Response
from .utils import request_suggestions, call_gemini_api, parse_gemini_response
from common.middleware import authenticate
# -------------------------
# Dashboard - Shows all projects
# -------------------------


def dashboard(request):
    projects = Project.objects.all()
    return render(request, "probackendapp/dashboard.html", {"projects": projects})

# -------------------------
# Create a new project
# -------------------------


def create_project(request):
    if request.method == "POST":
        name = request.POST.get("name")
        about = request.POST.get("about")
        if name:
            project = Project(name=name, about=about)
            project.save()
            return redirect("probackendapp:project_setup_description", str(project.id))
    return render(request, "probackendapp/create_project.html")

# -------------------------
# Set collection description and get suggestions from Gemini API


def generate_ai_images_page(request, collection_id):
    from .models import Collection
    collection = Collection.objects.get(id=collection_id)
    return render(request, "probackendapp/generate_ai_images.html", {"collection": collection})


# -------------------------


def project_setup_description(request, project_id):
    try:
        project = Project.objects.get(id=project_id)
    except DoesNotExist:
        return redirect("probackendapp:dashboard")

    # Check if a collection already exists for this project
    collection = Collection.objects(project=project).first()

    if request.method == "POST":
        description = request.POST.get("description", "").strip()
        uploaded_image = request.FILES.get("uploaded_image")

        # Create a new collection if not found
        if not collection:
            collection = Collection(project=project)
            item = CollectionItem()
            collection.items.append(item)
        else:
            # Use the first item (or create if missing)
            item = collection.items[0] if collection.items else CollectionItem(
            )
            if not collection.items:
                collection.items.append(item)

        # Update collection description
        collection.description = description

        # Handle uploaded image
        if uploaded_image:
            item.uploaded_theme_images.append(uploaded_image)

        # Generate suggestions (refresh on each submit)
        suggestions = request_suggestions(description, uploaded_image)
        item.suggested_themes = suggestions.get("themes", [])
        item.suggested_backgrounds = suggestions.get("backgrounds", [])
        item.suggested_poses = suggestions.get("poses", [])
        item.suggested_locations = suggestions.get("locations", [])
        item.suggested_colors = suggestions.get("colors", [])

        collection.save()

        return redirect("probackendapp:project_setup_select", str(project.id), str(collection.id))

    # For GET request — show existing description
    existing_description = collection.description if collection else ""

    return render(request, "probackendapp/project_setup_description.html", {
        "project": project,
        "existing_description": existing_description,
        "collection_exists": bool(collection),
        "collection_id": str(collection.id) if collection else None,
    })

# -------------------------
# Step 2: User selects / refines → Generate final moodboard prompts
# -------------------------
# from django.shortcuts import render, redirect
# from django.http import Response
# from mongoengine.errors import DoesNotExist
# import json
# from .models import Project, Collection, CollectionItem
# from .utils import request_suggestions, call_gemini_api
# def project_setup_select(request, project_id, collection_id):
#     try:
#         project = Project.objects.get(id=project_id)
#         collection = Collection.objects.get(id=collection_id, project=project)
#     except DoesNotExist:
#         return redirect("probackendapp:dashboard")

#     # Use first item or create a new one
#     item = collection.items[0] if collection.items else CollectionItem()
#     if not collection.items:
#         collection.items.append(item)
#         collection.save()

#     ai_response = {}
#     detailed_prompt_text = ""
#     ai_json_text = ""  # initialize

#     if request.method == "POST" and request.POST.get("action") == "save":
#         def getlist(name):
#             return request.POST.getlist(name)

#         # Save user selections
#         item.selected_themes = getlist("themes") or []
#         item.selected_backgrounds = getlist("backgrounds") or []
#         item.selected_poses = getlist("poses") or []
#         item.selected_locations = getlist("locations") or []
#         item.selected_colors = getlist("colors") or []

#         # Save uploaded images for each category
#         for category in ["theme", "background", "pose", "location", "color"]:
#             files = request.FILES.getlist(f"uploaded_{category}_images")
#             if files:
#                 getattr(item, f"uploaded_{category}_images").extend(files)

#         # Prepare uploaded images info
#         uploaded_images_info = ""
#         for cat in ["theme", "background", "pose", "location", "color"]:
#             imgs = getattr(item, f"uploaded_{cat}_images")
#             if imgs:
#                 uploaded_images_info += f"{cat.capitalize()} references: {', '.join([str(f) for f in imgs])}\n"

#         # -----------------------------
#         # Build Gemini AI structured prompt
#         # -----------------------------
#         gemini_prompt = f"""
# You are a professional creative AI assistant. Analyze the collection description and user selections carefully and generate structured image generation prompts.

# Collection Description: {collection.description}
# Selected Themes: {', '.join(item.selected_themes) or 'None'}
# Selected Backgrounds: {', '.join(item.selected_backgrounds) or 'None'}
# Selected Poses: {', '.join(item.selected_poses) or 'None'}
# Selected Locations: {', '.join(item.selected_locations) or 'None'}
# Selected Colors: {', '.join(item.selected_colors) or 'None'}
# Uploaded Image References: {uploaded_images_info if uploaded_images_info else 'None'}

# Generate prompts for the following 5 types. Explain each prompt clearly in context of the collection. Respond ONLY in valid JSON:
# {{
#     "white_background": "Prompt for white background images of the ornament, sharp, clean, isolated.",
#     "background_replace": "Prompt for images with themed backgrounds while keeping the ornament identical.",
#     "model_image": "Prompt to generate realistic model wearing the ornament. Model face and body must be accurate. Match selected poses and expressions, photo should focused mainly on the ornament.",
#     "campaign_image": "Prompt for campaign/promotional shots with models wearing ornaments in themed backgrounds, stylish composition.",

# }}
# """

#         # -----------------------------
#         # Call Gemini API and parse result
#         # -----------------------------
#         ai_json_text = call_gemini_api(gemini_prompt)

#         # Use the proper parsing function from utils
#         ai_response = parse_gemini_response(ai_json_text)

#         # Debug logging
#         print("=== Raw Gemini Response ===")
#         print(ai_json_text)
#         print("=== Parsed Response ===")
#         print(ai_response)
#         print("==========================")

#         # If parsing failed or response is empty, provide fallback
#         if not ai_response or "error" in ai_response or not isinstance(ai_response, dict):
#             print("Using fallback prompts due to parsing issues")
#             ai_response = {
#                 "white_background": "Professional product photography with clean white background, studio lighting, sharp focus on ornament details",
#                 "background_replace": "Same ornament with themed background replacement, maintaining product integrity and lighting",
#                 "model_image": "Realistic model wearing the ornament, professional fashion photography, accurate facial features and body proportions,photo should focused mainly on the ornament",
#                 "campaign_image": "Stylish campaign shot with model in themed setting, creative composition, promotional quality",

#             }

#         # Ensure all required keys exist
#         required_keys = ["white_background", "background_replace", "model_image", "campaign_image"]
#         for key in required_keys:
#             if key not in ai_response or not ai_response[key]:
#                 ai_response[key] = f"Generated prompt for {key.replace('_', ' ')} based on your collection theme"

#         # Save prompts in item
#         item.final_moodboard_prompt = gemini_prompt
#         item.moodboard_explanation = ai_json_text
#         item.generated_prompts = ai_response
#         collection.save()


#     # -----------------------------
#     # Prepare context for template
#     # -----------------------------
#     context = {
#     "project": project.name,
#     "collection": collection,  # pass full object so you can use collection.id in template
#     "item": 0,
#     "themes": item.selected_themes or item.suggested_themes,
#     "backgrounds": item.selected_backgrounds or item.suggested_backgrounds,
#     "poses": item.selected_poses or item.suggested_poses,
#     "locations": item.selected_locations or item.suggested_locations,
#     "colors": item.selected_colors or item.suggested_colors,
#     "item_obj": item,
#     "ai_response": ai_response,
#     "detailed_prompt_text": detailed_prompt_text,
#     "generate_ai_url": f"/probackendapp/generate_ai_images/{collection.id}/",  # pass full URL
# }

#     return render(request, "probackendapp/project_setup_select.html", context)


def project_setup_select(request, project_id, collection_id):
    try:
        project = Project.objects.get(id=project_id)
        collection = Collection.objects.get(id=collection_id, project=project)
    except DoesNotExist:
        return redirect("probackendapp:dashboard")

    # Get first item or create a new one if empty
    item = collection.items[0] if collection.items else CollectionItem()
    if not collection.items:
        collection.items.append(item)
        collection.save()

    # Use previously generated prompts if exist
    ai_response = item.generated_prompts or {}
    detailed_prompt_text = item.moodboard_explanation or ""

    if request.method == "POST" and request.POST.get("action") == "save":
        def getlist(name):
            return request.POST.getlist(name)

        # -----------------------------
        # Save selected options
        # -----------------------------
        item.selected_themes = getlist("themes") or []
        item.selected_backgrounds = getlist("backgrounds") or []
        item.selected_poses = getlist("poses") or []
        item.selected_locations = getlist("locations") or []
        item.selected_colors = getlist("colors") or []

        # Save uploaded images for each category
        for category in ["theme", "background", "pose", "location", "color"]:
            files = request.FILES.getlist(f"uploaded_{category}_images")
            if files:
                getattr(item, f"uploaded_{category}_images").extend(files)

        # Prepare uploaded images info for Gemini prompt
        uploaded_images_info = ""
        for cat in ["theme", "background", "pose", "location", "color"]:
            imgs = getattr(item, f"uploaded_{cat}_images")
            if imgs:
                uploaded_images_info += f"{cat.capitalize()} references: {', '.join([str(f) for f in imgs])}\n"

        # -----------------------------
        # Build Gemini AI structured prompt
        # -----------------------------
        gemini_prompt = f"""
You are a professional creative AI assistant. Analyze the collection description and user selections carefully and generate structured image generation prompts.

Collection Description: {collection.description}
Selected Themes: {', '.join(item.selected_themes) or 'None'}
Selected Backgrounds: {', '.join(item.selected_backgrounds) or 'None'}
Selected Poses: {', '.join(item.selected_poses) or 'None'}
Selected Locations: {', '.join(item.selected_locations) or 'None'}
Selected Colors: {', '.join(item.selected_colors) or 'None'}
Uploaded Image References: {uploaded_images_info if uploaded_images_info else 'None'}

Generate prompts for the following 4 types. Respond ONLY in valid JSON:
{{
    "white_background": "Prompt for white background images of the ornament, sharp, clean, isolated.",
    "background_replace": "Prompt for images with themed backgrounds while keeping the ornament identical.",
    "model_image": "Prompt to generate realistic model wearing the ornament. Model face and body must be accurate. Match selected poses and expressions, photo should focused mainly on the ornament.",
    "campaign_image": "Prompt for campaign/promotional shots with models wearing ornaments in themed backgrounds, stylish composition."
}}
"""

        # -----------------------------
        # Call Gemini API and parse result
        # -----------------------------
        ai_json_text = call_gemini_api(gemini_prompt)
        ai_response = parse_gemini_response(ai_json_text)

        # Fallback if parsing failed
        if not ai_response or "error" in ai_response or not isinstance(ai_response, dict):
            ai_response = {
                "white_background": "Professional product photography with clean white background, studio lighting, sharp focus on ornament details",
                "background_replace": "Same ornament with themed background replacement, maintaining product integrity and lighting",
                "model_image": "Realistic model wearing the ornament, professional fashion photography, accurate facial features and body proportions, photo focused mainly on the ornament",
                "campaign_image": "Stylish campaign shot with model in themed setting, creative composition, promotional quality",
            }

        # Ensure all keys exist
        for key in ["white_background", "background_replace", "model_image", "campaign_image"]:
            if key not in ai_response or not ai_response[key]:
                ai_response[key] = f"Generated prompt for {key.replace('_', ' ')} based on your collection theme"

        # Save prompts in item
        item.final_moodboard_prompt = gemini_prompt
        item.moodboard_explanation = ai_json_text
        item.generated_prompts = ai_response
        collection.save()

        # Refresh detailed_prompt_text to show in template
        detailed_prompt_text = ai_json_text

    # -----------------------------
    # Prepare context for template
    # -----------------------------
    # context = {
    #     "project": project.name,
    #     "collection": collection,  # full object for template
    #     "item_obj": item,
    #     "themes": item.selected_themes or item.suggested_themes,
    #     "backgrounds": item.selected_backgrounds or item.suggested_backgrounds,
    #     "poses": item.selected_poses or item.suggested_poses,
    #     "locations": item.selected_locations or item.suggested_locations,
    #     "colors": item.selected_colors or item.suggested_colors,
    #     "ai_response": ai_response,
    #     "detailed_prompt_text": detailed_prompt_text,
    #     "generate_ai_url": f"/probackendapp/generate_ai_images/{collection.id}/",
    # }
    def merge_unique(selected, suggested):
        """Merge selected and suggested items, removing duplicates while preserving order"""
        combined = list(suggested or [])
        for val in selected or []:
            if val not in combined:
                combined.append(val)
        return combined

    def categorize_options(selected, suggested):
        """Categorize options into suggested, selected, and combined for better display"""
        suggested_only = [item for item in (
            suggested or []) if item not in (selected or [])]
        selected_only = [item for item in (
            selected or []) if item not in (suggested or [])]
        both = [item for item in (selected or []) if item in (suggested or [])]

        return {
            'suggested_only': suggested_only,
            'selected_only': selected_only,
            'both': both,
            'all': merge_unique(selected, suggested)
        }

    context = {
        "project": project.name,
        "collection": collection,
        "item_obj": item,
        "themes": merge_unique(item.selected_themes, item.suggested_themes),
        "backgrounds": merge_unique(item.selected_backgrounds, item.suggested_backgrounds),
        "poses": merge_unique(item.selected_poses, item.suggested_poses),
        "locations": merge_unique(item.selected_locations, item.suggested_locations),
        "colors": merge_unique(item.selected_colors, item.suggested_colors),
        "themes_categorized": categorize_options(item.selected_themes, item.suggested_themes),
        "backgrounds_categorized": categorize_options(item.selected_backgrounds, item.suggested_backgrounds),
        "poses_categorized": categorize_options(item.selected_poses, item.suggested_poses),
        "locations_categorized": categorize_options(item.selected_locations, item.suggested_locations),
        "colors_categorized": categorize_options(item.selected_colors, item.suggested_colors),
        "ai_response": ai_response,
        "detailed_prompt_text": detailed_prompt_text,
        "generate_ai_url": f"/probackendapp/generate_ai_images/{collection.id}/",
    }

    return render(request, "probackendapp/project_setup_select.html", context)


try:
    from google import genai
    from google.genai import types
    has_genai = True
except ImportError:
    has_genai = False

# def generate_ai_images(request, collection_id):
#     if request.method != "POST":
#         return Response({"error": "Invalid request method."})

#     try:
#         collection = Collection.objects.get(id=collection_id)
#         description = collection.description
#         generated_images = []

#         if has_genai:
#             client = genai.Client(api_key=settings.GOOGLE_API_KEY)
#             model_name = "gemini-2.5-flash-image-preview"

#             for i in range(4):
#                 contents = [
#                     {"text": f"Generate a realistic human model image (face and shoulders visible) that model should sutalbe to the description of the collection and every model should be different: {description}. High-quality, photorealistic."}
#                 ]
#                 config = types.GenerateContentConfig(response_modalities=[types.Modality.IMAGE])
#                 resp = client.models.generate_content(model=model_name, contents=contents, config=config)
#                 candidate = resp.candidates[0]

#                 image_bytes = None
#                 for part in candidate.content.parts:
#                     if part.inline_data:
#                         data = part.inline_data.data
#                         image_bytes = data if isinstance(data, bytes) else base64.b64decode(data)
#                         break

#                 if not image_bytes:
#                     continue

#                 buf = io.BytesIO(image_bytes)
#                 buf.seek(0)
#                 upload_result = cloudinary.uploader.upload(
#                     buf,
#                     folder="collection_ai_models",
#                     public_id=f"collection_{collection.id}_{i+1}",
#                     overwrite=True
#                 )
#                 generated_images.append(upload_result['secure_url'])

#         else:
#             return Response({"error": "Gemini SDK not available."})

#         return Response({"images": generated_images})

#     except Exception as e:
#         traceback.print_exc()
#         return Response({"error": str(e)})


def generate_ai_images(request, collection_id):
    if request.method != "POST":
        return Response({"error": "Invalid request method."})

    try:
        collection = Collection.objects.get(id=collection_id)
        description = collection.description
        generated_images = []

        if has_genai:
            client = genai.Client(api_key=settings.GOOGLE_API_KEY)
            model_name = "gemini-2.5-flash-image-preview"

            for i in range(4):
                prompt_text = (
                    f"Generate a realistic human model image (face and shoulders visible) "
                    f"suitable for the collection description: {description}. "
                    f"High-quality, photorealistic."
                )

                contents = [{"role": "user", "parts": [{"text": prompt_text}]}]
                try:
                    resp = client.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            response_modalities=[types.Modality.IMAGE]
                        ),
                    )

                    if not resp.candidates:
                        print("⚠️ No candidates returned:", resp)
                        continue

                    candidate = resp.candidates[0]
                    if not getattr(candidate, "content", None):
                        print("⚠️ Candidate has no content:", candidate)
                        continue

                    image_bytes = None
                    for part in candidate.content.parts:
                        if hasattr(part, "inline_data") and part.inline_data:
                            data = part.inline_data.data
                            image_bytes = (
                                data if isinstance(
                                    data, bytes) else base64.b64decode(data)
                            )
                            break

                    if not image_bytes:
                        print("⚠️ No image data found in parts.")
                        continue

                    buf = io.BytesIO(image_bytes)
                    buf.seek(0)
                    upload_result = cloudinary.uploader.upload(
                        buf,
                        folder="collection_ai_models",
                        public_id=f"collection_{collection.id}_{i+1}",
                        overwrite=True,
                    )
                    generated_images.append(upload_result["secure_url"])

                    # Track AI model generation in history
                    try:
                        from .history_utils import track_project_image_generation
                        track_project_image_generation(
                            user_id=str(request.user.id),
                            collection_id=str(collection.id),
                            image_type="project_ai_model_generation",
                            image_url=upload_result["secure_url"],
                            prompt=prompt_text,
                            metadata={
                                "action": "ai_model_generation",
                                "model_index": i+1,
                                "total_generated": len(generated_images)
                            }
                        )
                    except Exception as history_error:
                        print(
                            f"Error tracking AI model generation history: {history_error}")

                except Exception as gen_err:
                    print("❌ Error generating image:", gen_err)
                    continue
        else:
            return Response({"error": "Gemini SDK not available."})

        # ✅ Get already saved images from the collection
        saved_images = []
        if collection.items and hasattr(collection.items[0], "generated_model_images"):
            saved_images = [img.get(
                "cloud") for img in collection.items[0].generated_model_images if "cloud" in img]

        return Response({
            "images": generated_images,
            "saved_images": saved_images
        })

    except Exception as e:
        traceback.print_exc()
        return Response({"error": str(e)})


# def save_generated_images(request, collection_id):
#     if request.method != "POST":
#         return Response({"success": False, "error": "Invalid request method."})

#     try:
#         data = json.loads(request.body)
#         selected_images = data.get("images", [])

#         if not selected_images:
#             return Response({"success": False, "error": "No images selected."})

#         collection = Collection.objects.get(id=collection_id)

#         if not collection.items:
#             return Response({"success": False, "error": "No items found in collection."})

#         item = collection.items[0]  # Assuming single item per collection

#         # Ensure field exists
#         if not hasattr(item, "generated_model_images"):
#             item.generated_model_images = []

#         saved_images = []
#         local_dir = os.path.join(settings.MEDIA_ROOT, "model_images")
#         os.makedirs(local_dir, exist_ok=True)

#         # Extract existing cloud URLs to avoid duplicates
#         existing_urls = {entry.get(
#             "cloud") for entry in item.generated_model_images if "cloud" in entry}

#         for url in selected_images:
#             if url in existing_urls:
#                 continue  # Skip duplicates

#             # Download image from Cloudinary
#             filename = url.split("/")[-1]
#             local_path = os.path.join(local_dir, filename)
#             resp = requests.get(url)
#             if resp.status_code == 200:
#                 with open(local_path, "wb") as f:
#                     f.write(resp.content)

#             # Save both paths (local + cloud)
#             entry = {"local": local_path, "cloud": url}
#             item.generated_model_images.append(entry)
#             saved_images.append(entry)

#         collection.save()

#         return Response({
#             "success": True,
#             "saved": saved_images,
#             "skipped_duplicates": len(selected_images) - len(saved_images)
#         })

#     except DoesNotExist:
#         return Response({"success": False, "error": "Collection not found."})
#     except Exception as e:
#         traceback.print_exc()
#         return Response({"success": False, "error": str(e)})


@authenticate
def save_generated_images(request, collection_id):
    if request.method != "POST":
        return Response({"success": False, "error": "Invalid request method."})

    try:
        data = json.loads(request.body)
        selected_images = set(data.get("images", []))

        collection = Collection.objects.get(id=collection_id)
        if not collection.items:
            return Response({"success": False, "error": "No items found in collection."})

        item = collection.items[0]

        # Existing images
        existing = item.generated_model_images or []
        existing_urls = {img.get("cloud")
                         for img in existing if "cloud" in img}

        local_dir = os.path.join(settings.MEDIA_ROOT, "model_images")
        os.makedirs(local_dir, exist_ok=True)

        # 1️⃣ Remove unselected images
        updated_images = [img for img in existing if img.get(
            "cloud") in selected_images]

        # 2️⃣ Add new ones
        for url in selected_images - existing_urls:
            filename = url.split("/")[-1]
            local_path = os.path.join(local_dir, filename)

            resp = requests.get(url)
            if resp.status_code == 200:
                with open(local_path, "wb") as f:
                    f.write(resp.content)

            updated_images.append({"local": local_path, "cloud": url})

        # Update and save
        item.generated_model_images = updated_images
        collection.save()

        # Track model image selection in history
        try:
            from .history_utils import track_project_image_generation
            for img in updated_images:
                if img.get("cloud"):
                    track_project_image_generation(
                        user_id="system",  # TODO: Get actual user ID from request
                        collection_id=str(collection.id),
                        image_type="project_model_selection",
                        image_url=img["cloud"],
                        prompt="Model image selected for project",
                        local_path=img.get("local"),
                        metadata={
                            "action": "model_selection",
                            "total_models": len(updated_images)
                        }
                    )
        except Exception as history_error:
            print(f"Error tracking model selection history: {history_error}")

        return Response({
            "success": True,
            "total_selected": len(selected_images),
            "stored_images": len(updated_images)
        })

    except Collection.DoesNotExist:
        return Response({"success": False, "error": "Collection not found."})
    except Exception as e:
        traceback.print_exc()
        return Response({"success": False, "error": str(e)})

# -------------------------
# Collection detail view
# -------------------------


def collection_detail(request, project_id, collection_id):
    collection = get_object_or_404(
        Collection, id=collection_id, project_id=project_id)
    return render(request, "probackendapp/collection_detail.html", {"collection": collection})


def upload_product_images_page(request, collection_id):
    from django.shortcuts import render
    collection = Collection.objects.get(id=collection_id)
    return render(request, "probackendapp/upload_product_images.html", {"collection": collection})


@authenticate
def upload_product_images_api(request, collection_id):
    if request.method != "POST":
        return Response({"success": False, "error": "Invalid request method."})

    try:
        collection = Collection.objects.get(id=collection_id)
        if not collection.items:
            return Response({"success": False, "error": "No items found in collection."})

        item = collection.items[0]  # assuming single item per collection
        uploaded_files = request.FILES.getlist("images")

        if not uploaded_files:
            return Response({"success": False, "error": "No images uploaded."})

        local_dir = os.path.join(settings.MEDIA_ROOT, "product_images")
        os.makedirs(local_dir, exist_ok=True)

        new_product_images = []

        for file in uploaded_files:
            upload_result = cloudinary.uploader.upload(
                file,
                folder="collection_product_images",
                overwrite=True
            )
            cloud_url = upload_result.get("secure_url")

            local_path = os.path.join(local_dir, file.name)
            with open(local_path, "wb") as f:
                for chunk in file.chunks():
                    f.write(chunk)

            # ✅ Create EmbeddedDocument object instead of dict
            product_img = ProductImage(
                uploaded_image_url=cloud_url,
                uploaded_image_path=local_path,
                generated_images=[]
            )

            new_product_images.append(product_img)

        # ✅ Append properly
        if not hasattr(item, "product_images"):
            item.product_images = []
        item.product_images.extend(new_product_images)

        # ✅ Save back properly to MongoEngine
        collection.items[0] = item
        collection.save()

        # Track product image uploads in history
        try:
            from .history_utils import track_project_image_generation
            user_id = str(request.user.id) if hasattr(
                request, 'user') and request.user else "system"
            for product_img in new_product_images:
                track_project_image_generation(
                    user_id=user_id,
                    collection_id=str(collection.id),
                    image_type="project_product_upload",
                    image_url=product_img.uploaded_image_url,
                    prompt="Product image uploaded to project",
                    local_path=product_img.uploaded_image_path,
                    metadata={
                        "action": "product_upload",
                        "total_products": len(new_product_images)
                    }
                )
        except Exception as history_error:
            print(f"Error tracking product upload history: {history_error}")

        return Response({"success": True, "count": len(new_product_images)})

    except Exception as e:
        traceback.print_exc()
        return Response({"success": False, "error": str(e)})


def generate_product_model_page(request, collection_id):
    """Render the template with product images and available model images"""
    try:
        collection = Collection.objects.get(id=collection_id)
        item = collection.items[0]

        product_images = item.product_images if hasattr(
            item, "product_images") else []
        model_images = item.generated_model_images if hasattr(
            item, "generated_model_images") else []

        return render(request, "probackendapp/generate_product_model.html", {
            "collection": collection,
            "product_images": product_images,
            "model_images": model_images,
        })
    except Exception as e:
        traceback.print_exc()
        return Response({"success": False, "error": str(e)}, status=500)


@csrf_exempt
def generate_product_model_api(request, collection_id):
    """
    Generate composite AI image combining a product and selected model
    using Gemini, aligning naturally with realistic shadows & lighting.
    """
    try:
        collection = Collection.objects.get(id=collection_id)
        item = collection.items[0]

        product_url = request.POST.get("product_url")
        model_url = request.POST.get("model_url")
        prompt_text = request.POST.get("prompt")

        if not all([product_url, model_url, prompt_text]):
            return Response({"success": False, "error": "Missing data."})

        if not settings.GOOGLE_API_KEY:
            return Response({"success": False, "error": "GOOGLE_API_KEY not configured."})

        # ✅ Initialize Gemini client
        client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        model_name = "gemini-2.5-flash-image-preview"

        import requests
        import base64
        import os
        import uuid

        # Download both images
        product_data = base64.b64encode(
            requests.get(product_url).content).decode("utf-8")
        model_data = base64.b64encode(
            requests.get(model_url).content).decode("utf-8")

        contents = [
            {"inline_data": {"mime_type": "image/jpeg", "data": model_data}},
            {"inline_data": {"mime_type": "image/jpeg", "data": product_data}},
            {"text": f"Place the product naturally on the model according to this prompt: {prompt_text}. Maintain realism, shadows, proportions, and lighting."}
        ]

        config = types.GenerateContentConfig(
            response_modalities=[types.Modality.IMAGE])

        resp = client.models.generate_content(
            model=model_name, contents=contents, config=config)

        candidate = resp.candidates[0]
        generated_bytes = None
        for part in candidate.content.parts:
            if part.inline_data and part.inline_data.data:
                data = part.inline_data.data
                generated_bytes = data if isinstance(
                    data, bytes) else base64.b64decode(data)
                break

        if not generated_bytes:
            return Response({"success": False, "error": "Gemini did not return an image."})

        # Save locally
        output_dir = os.path.join("media", "composite_images", str(
            collection_id), str(uuid.uuid4()))
        os.makedirs(output_dir, exist_ok=True)
        local_path = os.path.join(output_dir, "composite.png")
        with open(local_path, "wb") as f:
            f.write(generated_bytes)

        # Upload to Cloudinary
        import cloudinary.uploader
        cloud_upload = cloudinary.uploader.upload(
            local_path,
            folder=f"ai_studio/composite/{collection_id}/{uuid.uuid4()}/",
            use_filename=True,
            unique_filename=False,
            resource_type="image"
        )

        result = {
            "url": cloud_upload["secure_url"],
            "path": local_path
        }

        return Response({"success": True, "image": result})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({"success": False, "error": str(e)}, status=500)


# @csrf_exempt
# def generate_all_product_model_images(request, collection_id):
#     """
#     Generate AI images for all product images in a collection using a local model image
#     and prompts stored in `generated_prompts`. Saves both locally and in Cloudinary.
#     """
#     import os
#     import base64
#     import uuid
#     import requests
#     import traceback
#     import cloudinary.uploader

#     try:
#         collection = Collection.objects.get(id=collection_id)
#         item = collection.items[0]
#         body = json.loads(request.body.decode("utf-8"))

#         # Local model image path (you can adjust where it is stored)
#         model_local_path = body.get("model_local_path")
#         print(model_local_path)
#         if not os.path.exists(model_local_path):
#             return Response({"success": False, "error": "Local model image not found."})

#         # Ensure prompts exist
#         if not hasattr(item, "generated_prompts") or not item.generated_prompts:
#             return Response({"success": False, "error": "No generated prompts found."})

#         # Read model image once
#         with open(model_local_path, "rb") as f:
#             model_bytes = f.read()
#         model_b64 = base64.b64encode(model_bytes).decode("utf-8")

#         client = genai.Client(api_key=settings.GOOGLE_API_KEY)
#         model_name = "gemini-2.5-flash-image-preview"

#         # Loop through each uploaded product image
#         for product in item.product_images:  # adjust field name
#             product_path = product.uploaded_image_path
#             if not os.path.exists(product_path):
#                 print(f"⚠️ Product image not found: {product_path}")
#                 continue

#             with open(product_path, "rb") as f:
#                 product_bytes = f.read()
#             product_b64 = base64.b64encode(product_bytes).decode("utf-8")

#             generated_dict = {}
#             prompt_templates = {
#     "white_background": (
#         "Create a product photo with a clean, elegant white background. "
#         "The product should be centered, well-lit with studio lighting, and displayed naturally. "
#         "Keep reflections, shadows, and proportions realistic. "
#         "Follow this specific style prompt: {prompt_text}"
#     ),
#     "background_replace": (
#         "Replace the background of the product image with one that enhances its visual appeal "
#         "and makes the product stand out. Ensure correct positioning, perspective, and realistic lighting. "
#         "Follow this specific style prompt: {prompt_text}"
#     ),
#     "model_image": (
#         "Overlay or dress the uploaded model with the product realistically. "
#         "Ensure proportions, fitting, and lighting match naturally. "
#         "Make it elegant and fashion-photography style. "
#         "Follow this specific style prompt: {prompt_text}"
#     ),
#     "campaign_image": (
#         "Create a professional campaign shot where the model is wearing the product in a lifestyle or editorial setting. "
#         "Use cinematic lighting, balanced colors, and realistic shadow integration. "
#         "The overall output should look like a magazine photoshoot. "
#         "Follow this specific style prompt: {prompt_text}"
#     ),
# }

#             # Generate images for each prompt key
#             for key, prompt_text in item.generated_prompts.items():
#                 try:
#                     contents = [
#                         {"inline_data": {"mime_type": "image/jpeg", "data": model_b64}},
#                         {"inline_data": {"mime_type": "image/jpeg", "data": product_b64}},
#                         {"text": f"Place the product naturally on the model according to this prompt: {prompt_text}. Maintain realism, shadows, proportions, and lighting."}
#                     ]

#                     config = types.GenerateContentConfig(
#                         response_modalities=[types.Modality.IMAGE])

#                     resp = client.models.generate_content(
#                         model=model_name, contents=contents, config=config
#                     )

#                     candidate = resp.candidates[0]
#                     generated_bytes = None
#                     for part in candidate.content.parts:
#                         if part.inline_data and part.inline_data.data:
#                             data = part.inline_data.data
#                             generated_bytes = data if isinstance(
#                                 data, bytes) else base64.b64decode(data)
#                             break

#                     if not generated_bytes:
#                         print(
#                             f"⚠️ No image returned for {key} of {product.uploaded_image_url}")
#                         continue

#                     # Save locally
#                     output_dir = os.path.join("media", "composite_images", str(
#                         collection_id), str(uuid.uuid4()))
#                     os.makedirs(output_dir, exist_ok=True)
#                     local_path = os.path.join(output_dir, f"{key}.png")
#                     with open(local_path, "wb") as f:
#                         f.write(generated_bytes)

#                     # Upload to Cloudinary
#                     cloud_upload = cloudinary.uploader.upload(
#                         local_path,
#                         folder=f"ai_studio/composite/{collection_id}/{uuid.uuid4()}/",
#                         use_filename=True,
#                         unique_filename=False,
#                         resource_type="image"
#                     )

#                     generated_dict[key] = {
#                         "url": cloud_upload["secure_url"],
#                         "path": local_path
#                     }

#                 except Exception as e:
#                     traceback.print_exc()
#                     print(
#                         f"⚠️ Failed to generate {key} for {product.uploaded_image_url}: {e}")
#                     continue

#             # Save generated images for this product
#             product.generated_images = generated_dict

#         # Save collection after all images generated
#         collection.save()
#         return Response({"success": True, "message": "All product model images generated successfully."})

#     except Exception as e:
#         traceback.print_exc()
#         return Response({"success": False, "error": str(e)}, status=500)


def generate_all_product_model_images(request, collection_id):
    """
    Generate AI images for all product images in a collection using the selected model image
    and prompts stored in `generated_prompts`. Saves both locally and in Cloudinary.
    """
    import os
    import base64
    import uuid
    import json
    import traceback
    import cloudinary.uploader
    from datetime import datetime
    from google import genai
    from google.genai import types
    from django.conf import settings
    # Use rest_framework.response.Response (already imported at top of file)

    try:
        # ---------------------------
        # 1. Fetch collection and setup
        # ---------------------------
        collection = Collection.objects.get(id=collection_id)
        item = collection.items[0]  # Assuming single-item collection setup

        # Get the selected model from the collection
        if not hasattr(item, 'selected_model') or not item.selected_model:
            return Response({"success": False, "error": "No model selected. Please select a model first."})

        selected_model = item.selected_model
        model_local_path = selected_model.get("local")

        if not model_local_path or not os.path.exists(model_local_path):
            return Response({"success": False, "error": "Selected model image not found on server."})

        if not hasattr(item, "generated_prompts") or not item.generated_prompts:
            return Response({"success": False, "error": "No generated prompts found."})

        # ---------------------------
        # 2. Read model image once
        # ---------------------------
        with open(model_local_path, "rb") as f:
            model_bytes = f.read()
        model_b64 = base64.b64encode(model_bytes).decode("utf-8")

        client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        model_name = "gemini-2.5-flash-image-preview"

        # ---------------------------
        # 3. Prompt templates
        # ---------------------------
        # prompt_templates = {
        #     "white_background": (
        #         "make sure to display the product image which is present in the product_image_path dont chnage the product image"
        #         "Create a product photo with a clean, elegant white background. "
        #         "The product should be centered, well-lit with studio lighting, and displayed naturally. "
        #         "Keep reflections, shadows, and proportions realistic. "
        #         "Follow this specific style prompt: {prompt_text}"
        #     ),
        #     "background_replace": (
        #         "make sure to display the product image which is present in the product_image_path dont chnage the product image"
        #         "Replace the background of the product image with one that enhances its visual appeal "
        #         "and makes the product stand out. Ensure correct positioning, perspective, and realistic lighting. "
        #         "Follow this specific style prompt: {prompt_text}"
        #     ),
        #     "model_image": (
        #         "make sure to display the product image which is present in the product_image_path dont chnage the product image"
        #         "Overlay or dress the uploaded model with the product realistically. "
        #         "Ensure proportions, fitting, and lighting match naturally. "
        #         "Make it elegant and fashion-photography style. "
        #         "make sure that the model is wearing only the product image "
        #         "Follow this specific style prompt: {prompt_text}"
        #     ),
        #     "campaign_image": (
        #         "make sure to display the product image which is present in the product_image_path dont chnage the product image"
        #         "Create a professional campaign shot where the model is wearing only the product in a lifestyle or editorial setting. "
        #         "Use cinematic lighting, balanced colors, and realistic shadow integration. "
        #         "The overall output should look like a magazine photoshoot. "
        #         "Follow this specific style prompt: {prompt_text}"
        #     ),
        # }

        # Get prompt templates from database with fallback
        from .prompt_initializer import get_prompt_from_db

        default_white_bg = """Do NOT modify, alter, or redesign the product in any way — its color, shape, texture, and proportions must remain exactly the same.(important dont change the product image) 
Generate a high-quality product photo on a clean, elegant white studio background. 
The product should appear exactly as in the input image, only placed against a professional white background. 
Ensure balanced, soft studio lighting with natural shadows and realistic reflections. 
Highlight product clarity and detail. 
Follow this specific style prompt: {prompt_text}"""

        default_bg_replace = """Replace only the background of the product image with one that enhances and highlights the ornament elegantly. 
Do NOT modify the product itself — preserve its original look, proportions, color, and texture exactly. 
The new background should create a professional photo-shoot vibe with proper lighting, depth, and composition. 
Ensure the product is the focal point of the frame and stands out naturally under studio lighting. 
Use soft shadows, realistic reflections, and balanced highlights. 
Follow this specific style prompt: {prompt_text}"""

        default_model = """Generate a realistic photo of the uploaded model (where the uploaded model is present in the model_image_path should be exactly the same) wearing ONLY the given product (such as an ornament or jewelry). 
Do NOT modify the product design or appearance. It must look identical to the provided product image. 
Ensure the product fits the model naturally and proportionally, with correct placement and lighting consistency. 
The overall image should have the quality of a professional fashion photo shoot with soft studio lighting and elegant composition. 
Follow this specific style prompt: {prompt_text}"""

        default_campaign = """Create a professional campaign-style image where the uploaded model (where the uploaded model is present in the model_image_path should be exactly the same) is wearing ONLY the given product, 
keeping the product exactly as it appears in the original product image — no changes in color, shape, or design. 
Use a lifestyle or editorial-style background that enhances the brand aesthetic while maintaining focus on the product. 
Ensure cinematic yet natural studio lighting, soft shadows, and high-end magazine-quality realism. 
Follow this specific style prompt: {prompt_text}"""

        prompt_templates = {
            "white_background": get_prompt_from_db('white_background_template', default_white_bg),
            "background_replace": get_prompt_from_db('background_replace_template', default_bg_replace),
            "model_image": get_prompt_from_db('model_image_template', default_model),
            "campaign_image": get_prompt_from_db('campaign_image_template', default_campaign),
        }

        # ---------------------------
        # 4. Loop through each product image
        # ---------------------------
        for product in item.product_images:
            product_path = product.uploaded_image_path

            if not os.path.exists(product_path):
                print(f"⚠️ Product image not found: {product_path}")
                continue

            with open(product_path, "rb") as f:
                product_bytes = f.read()
            product_b64 = base64.b64encode(product_bytes).decode("utf-8")

            # Clear any old generated images for this run
            product.generated_images = []

            # ---------------------------
            # 5. Generate images for each prompt
            # ---------------------------
            for key, prompt_text in item.generated_prompts.items():
                try:
                    template = prompt_templates.get(key, "")
                    if template:
                        custom_prompt = template.format(
                            prompt_text=prompt_text)
                    else:
                        custom_prompt = prompt_text

                    contents = [
                        {"inline_data": {"mime_type": "image/jpeg", "data": model_b64}},
                        {"inline_data": {"mime_type": "image/jpeg", "data": product_b64}},
                        {"text": custom_prompt},
                    ]

                    config = types.GenerateContentConfig(
                        response_modalities=[types.Modality.IMAGE]
                    )

                    resp = client.models.generate_content(
                        model=model_name, contents=contents, config=config
                    )

                    candidate = resp.candidates[0]
                    generated_bytes = None

                    for part in candidate.content.parts:
                        if part.inline_data and part.inline_data.data:
                            data = part.inline_data.data
                            generated_bytes = data if isinstance(
                                data, bytes) else base64.b64decode(data)
                            break

                    if not generated_bytes:
                        print(
                            f"⚠️ No image returned for {key} of {product.uploaded_image_url}")
                        continue

                    # ---------------------------
                    # 6. Save locally
                    # ---------------------------
                    output_dir = os.path.join(
                        "media", "composite_images", str(collection_id))
                    os.makedirs(output_dir, exist_ok=True)
                    local_path = os.path.join(
                        output_dir, f"{uuid.uuid4()}_{key}.png")

                    with open(local_path, "wb") as f:
                        f.write(generated_bytes)

                    # ---------------------------
                    # 7. Upload to Cloudinary
                    # ---------------------------
                    cloud_upload = cloudinary.uploader.upload(
                        local_path,
                        folder=f"ai_studio/composite/{collection_id}/{uuid.uuid4()}/",
                        use_filename=True,
                        unique_filename=False,
                        resource_type="image",
                    )

                    # ---------------------------
                    # 8. Store result in product with model tracking
                    # ---------------------------
                    product.generated_images.append({
                        "type": key,
                        "prompt": prompt_text,
                        "local_path": local_path,
                        "cloud_url": cloud_upload["secure_url"],
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "model_used": {
                            "type": selected_model.get("type"),
                            "local": selected_model.get("local"),
                            "cloud": selected_model.get("cloud"),
                            "name": selected_model.get("name", "")
                        }
                    })

                    # Track image generation in history
                    try:
                        from .history_utils import track_project_image_generation
                        track_project_image_generation(
                            user_id=str(request.user.id),
                            collection_id=str(collection.id),
                            image_type=f"project_{key}",
                            image_url=cloud_upload["secure_url"],
                            prompt=prompt_text,
                            local_path=local_path,
                            metadata={
                                "model_used": selected_model.get("type"),
                                "product_url": product.uploaded_image_url,
                                "model_name": selected_model.get("name", ""),
                                "generation_type": key
                            }
                        )
                    except Exception as history_error:
                        print(
                            f"Error tracking project image generation history: {history_error}")

                except Exception as e:
                    traceback.print_exc()
                    print(
                        f"⚠️ Failed to generate {key} for {product.uploaded_image_url}: {e}")
                    continue

        # ---------------------------
        # 9. Save updated collection
        # ---------------------------
        collection.save()

        total_generated = sum(len(p.generated_images)
                              for p in item.product_images)

        return Response({
            "success": True,
            "message": f"All product model images generated successfully ({total_generated} images).",
            "total_generated": total_generated,
        })

    except Exception as e:
        traceback.print_exc()
        return Response({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@authenticate
def regenerate_product_model_image(request, collection_id):
    """
    Regenerate a specific generated image using Google GenAI (Gemini).
    Allows specifying a different model (AI or real) for regeneration.
    Tracks model usage statistics.
    """
    import json
    import os
    import uuid
    import base64
    import traceback
    import cloudinary.uploader
    from datetime import datetime
    from google import genai
    from google.genai import types

    try:
        data = json.loads(request.body)
        product_image_path = data.get("product_image_path")
        generated_image_path = data.get("generated_image_path")
        new_prompt = data.get("prompt")
        use_different_model = data.get("use_different_model", False)
        # {type: 'ai'/'real', local: path, cloud: url}
        new_model_data = data.get("new_model")

        if not (product_image_path and generated_image_path):
            print("Missing parameters", product_image_path,
                  generated_image_path, new_prompt)
            return Response({"success": False, "error": "Missing parameters"}, status=400)

        # Load collection and item
        collection = Collection.objects.get(id=collection_id)
        item = collection.items[0]

        # Find the generated image we're regenerating and the product
        # This could be either an original generated image or a regenerated image
        target_generated = None
        target_product = None
        is_regenerated_image = False
        original_prompt = None

        for p in item.product_images:
            for g in p.generated_images:
                # Check if it's the original generated image
                if g.get("local_path") == generated_image_path:
                    target_generated = g
                    target_product = p
                    original_prompt = g.get("prompt")
                    break

                # Check if it's a regenerated image
                if "regenerated_images" in g:
                    for regen in g.get("regenerated_images", []):
                        if regen.get("local_path") == generated_image_path:
                            target_generated = g  # Store the parent generated image
                            target_product = p
                            is_regenerated_image = True
                            original_prompt = regen.get(
                                "prompt", g.get("prompt"))
                            break
                    if target_generated:
                        break
            if target_generated:
                break

        if not target_generated:
            return Response({"success": False, "error": "Generated image not found"}, status=404)

        # --- Google GenAI setup ---
        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        model_name = "gemini-2.5-flash-image-preview"

        # Determine which model to use
        if use_different_model and new_model_data:
            model_to_use = new_model_data
        else:
            # Use the same model that was originally used (from selected_model)
            model_to_use = item.selected_model if hasattr(
                item, 'selected_model') else None

        if not model_to_use:
            return Response({"success": False, "error": "No model specified for regeneration"})

        # Load model image
        model_local_path = model_to_use.get("local")
        if not model_local_path or not os.path.exists(model_local_path):
            return Response({"success": False, "error": "Model image not found"})

        with open(model_local_path, "rb") as f:
            model_bytes = f.read()
        model_b64 = base64.b64encode(model_bytes).decode("utf-8")

        # Load product image
        if not os.path.exists(product_image_path):
            return Response({"success": False, "error": "Product image not found"})

        with open(product_image_path, "rb") as f:
            product_bytes = f.read()
        product_b64 = base64.b64encode(product_bytes).decode("utf-8")

        # Build custom prompt based on the original image type
        # Combine original prompt context with new modifications
        original_type = target_generated.get("type", "model_image")
        original_base_prompt = target_generated.get("prompt", "")

        # Get regeneration prompts from database with fallback
        from .prompt_initializer import get_prompt_from_db

        # If using different model without new modifications, just use original prompt
        if use_different_model and (not new_prompt or not new_prompt.strip()):
            default_regenerate_white = "Generate a high-quality product photo on a clean, elegant white studio background. \nDo NOT modify the product - keep its color, shape, texture exactly the same. \n{original_prompt}"
            default_regenerate_bg = "Replace only the background elegantly while keeping the product identical. \n{original_prompt}"
            default_regenerate_model = "Generate a realistic photo of the model wearing ONLY the given product. \nKeep the product design identical to the original. \n{original_prompt}"
            default_regenerate_campaign = "Create a professional campaign-style image with the model wearing ONLY the product. \nKeep the product exactly as it appears in the original. \n{original_prompt}"

            regenerate_templates = {
                "white_background": get_prompt_from_db('regenerate_white_background_template', default_regenerate_white),
                "background_replace": get_prompt_from_db('regenerate_background_replace_template', default_regenerate_bg),
                "model_image": get_prompt_from_db('regenerate_model_image_template', default_regenerate_model),
                "campaign_image": get_prompt_from_db('regenerate_campaign_image_template', default_regenerate_campaign),
            }

            template = regenerate_templates.get(
                original_type, "{original_prompt}")
            custom_prompt = template.format(
                original_prompt=original_base_prompt)
        else:
            # Combine original prompt with modifications
            default_with_mods_white = "Generate a high-quality product photo on a clean, elegant white studio background. \nDo NOT modify the product - keep its color, shape, texture exactly the same. \nOriginal style: {original_prompt}. \nModifications: {new_prompt}"
            default_with_mods_bg = "Replace only the background elegantly while keeping the product identical. \nOriginal style: {original_prompt}. \nModifications: {new_prompt}"
            default_with_mods_model = "Generate a realistic photo of the model wearing ONLY the given product. \nKeep the product design identical to the original. \nOriginal style: {original_prompt}. \nModifications: {new_prompt}"
            default_with_mods_campaign = "Create a professional campaign-style image with the model wearing ONLY the product. \nKeep the product exactly as it appears in the original. \nOriginal style: {original_prompt}. \nModifications: {new_prompt}"

            # Use a generic template for modifications since we have specific ones per type
            regenerate_templates = {
                "white_background": get_prompt_from_db('regenerate_with_modifications_white', default_with_mods_white),
                "background_replace": get_prompt_from_db('regenerate_with_modifications_bg', default_with_mods_bg),
                "model_image": get_prompt_from_db('regenerate_with_modifications_model', default_with_mods_model),
                "campaign_image": get_prompt_from_db('regenerate_with_modifications_campaign', default_with_mods_campaign),
            }

            template = regenerate_templates.get(
                original_type, "Original: {original_prompt}. Modifications: {new_prompt}")
            custom_prompt = template.format(
                original_prompt=original_base_prompt,
                new_prompt=new_prompt or ""
            )

        # Generate with model and product
        contents = [
            {"inline_data": {"mime_type": "image/jpeg", "data": model_b64}},
            {"inline_data": {"mime_type": "image/jpeg", "data": product_b64}},
            {"text": custom_prompt}
        ]

        config = types.GenerateContentConfig(
            response_modalities=[types.Modality.IMAGE]
        )

        resp = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config
        )

        # Extract generated image bytes
        candidate = resp.candidates[0]
        generated_bytes = None
        for part in candidate.content.parts:
            if part.inline_data and part.inline_data.data:
                data_part = part.inline_data.data
                generated_bytes = data_part if isinstance(
                    data_part, bytes) else base64.b64decode(data_part)
                break

        if not generated_bytes:
            return Response({"success": False, "error": "No image generated by GenAI"})

        # --- Save new regenerated image locally ---
        new_filename = f"{uuid.uuid4()}_regenerated.png"
        local_dir = os.path.join(
            "media", "composite_images", str(collection_id))
        os.makedirs(local_dir, exist_ok=True)
        local_output_path = os.path.join(local_dir, new_filename)

        with open(local_output_path, "wb") as f:
            f.write(generated_bytes)

        # --- Upload to Cloudinary ---
        upload_result = cloudinary.uploader.upload(
            local_output_path,
            folder=f"ai_studio/regenerated/{collection_id}/"
        )
        cloud_url = upload_result["secure_url"]

        # --- Append regenerated image metadata with model tracking ---
        # This tracks which model was used for each regeneration, supporting both AI and Real models
        # Model count is calculated as: 1 (original) + len(regenerated_images)
        # Model types used are tracked in the model_used field for each version
        regenerated_data = {
            # Use new prompt if provided, otherwise original
            "prompt": new_prompt or original_base_prompt,
            "original_prompt": original_base_prompt,
            "combined_prompt": custom_prompt,
            "type": original_type,
            "local_path": local_output_path,
            "cloud_url": cloud_url,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "product_image_path": product_image_path,
            "model_used": {
                "type": model_to_use.get("type"),  # 'ai' or 'real'
                "local": model_to_use.get("local"),
                "cloud": model_to_use.get("cloud"),
                "name": model_to_use.get("name", "")
            }
        }

        target_generated.setdefault(
            "regenerated_images", []).append(regenerated_data)
        collection.save()

        # Track regeneration in history
        try:
            from .history_utils import track_image_regeneration
            track_image_regeneration(
                user_id=str(request.user.id),
                original_image_id=str(target_generated.get("id", "unknown")),
                new_image_url=cloud_url,
                new_prompt=new_prompt or "",
                original_prompt=original_base_prompt,
                image_type=original_type,
                project_id=str(collection.project.id),
                collection_id=str(collection.id),
                local_path=local_output_path,
                metadata={
                    "model_used": regenerated_data["model_used"],
                    "regeneration_count": len(target_generated.get("regenerated_images", [])),
                    "used_different_model": use_different_model
                }
            )
        except Exception as history_error:
            print(f"Error tracking regeneration history: {history_error}")

        return Response({
            "success": True,
            "url": cloud_url,
            "local_path": local_output_path,
            "model_used": regenerated_data["model_used"],
            "original_prompt": original_base_prompt,
            "new_prompt": new_prompt or "",
            "combined_prompt": custom_prompt,
            "type": original_type,
            "regeneration_count": len(target_generated.get("regenerated_images", [])),
            "product_image_url": target_product.uploaded_image_url,
            "used_different_model": use_different_model
        })

    except Exception as e:
        traceback.print_exc()
        return Response({"success": False, "error": str(e)}, status=500)
