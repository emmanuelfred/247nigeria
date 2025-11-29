from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
import boto3

bucket_name = settings.AWS_STORAGE_BUCKET_NAME
region = settings.AWS_S3_REGION_NAME
s3 = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
def upload_to_s3(file, bucket_name):
    s3.upload_fileobj(file, bucket_name, file.name,ExtraArgs={
            'ContentType': file.content_type
        })
    bucket_location = s3.get_bucket_location(Bucket=bucket_name)
    region = bucket_location['LocationConstraint']
    file_url = f"https://s3.{region}.amazonaws.com/{bucket_name}/{file.name.replace(' ', '+')}"
    return file_url

def get_s3_objects(bucket_name):

    response = s3.list_objects_v2(Bucket=bucket_name)
    if 'Contents' in response:
        return [obj['Key'] for obj in response['Contents']]
    return []


def upload_file(request):
    if request.method == 'POST' and request.FILES.get('file'):
        file = upload_to_s3(request.FILES['file'], settings.AWS_STORAGE_BUCKET_NAME)

        messages.success(request, "File uploaded successfully.")
        object_keys = get_s3_objects(settings.AWS_STORAGE_BUCKET_NAME)
        s3_url =f"https://s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{settings.AWS_STORAGE_BUCKET_NAME}/"
        images = [{'url': s3_url + key} for key in object_keys] 
        return render(request, 'home.html', {'images': images}) 
       

    object_keys = get_s3_objects(settings.AWS_STORAGE_BUCKET_NAME)
    s3_url = f"https://s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{settings.AWS_STORAGE_BUCKET_NAME}/"
    images = [{'url': s3_url + key} for key in object_keys]
    
    return render(request, 'home.html', {'images': images})






























def delete_image(request):
    if request.method == 'POST':
        image_key = request.POST.get('image_key')
        print(image_key)
        object_key = image_key.split(f"{bucket_name}/")[1]
        
        try:
            s3.delete_object(Bucket=bucket_name, Key=object_key)
            messages.success(request, "File deleted successfully.")
        except Exception as e:
            messages.error(request, f"Error deleting image: {str(e)}")
        
        return redirect('upload')
   
