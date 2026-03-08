# Supabase Configuration

## Project Details

**Project:** ranch-view
**Project ID:** dtzayqhebbrbvordmabh
**API URL:** https://dtzayqhebbrbvordmabh.supabase.co

## Storage Bucket

**Bucket Name:** `spypoint-images` (PUBLIC bucket)
**Camera Folder:** `tophand-zero-04`

### Upload Path Structure

Images are uploaded to:
```
spypoint-images/
  └── tophand-zero-04/
      └── YYYY/
          └── MM/
              └── DD/
                  └── tophand-zero-04_YYYYMMDD_HHMMSS.jpg
```

Example: `spypoint-images/tophand-zero-04/2026/03/08/tophand-zero-04_20260308_143022.jpg`

## API Credentials

Stored in systemd service environment variables:

- **SUPABASE_URL:** `https://dtzayqhebbrbvordmabh.supabase.co`
- **SUPABASE_KEY:** Service role key (see ranch-camera.service)
- **SUPABASE_BUCKET:** `spypoint-images`

## S3 API Access (Alternative)

If needed, Supabase Storage also supports S3 protocol:

- **S3 Endpoint:** `https://dtzayqhebbrbvordmabh.storage.supabase.co/storage/v1/s3`
- **Region:** `us-west-2`

## Deployment

The Supabase configuration is deployed via:

```bash
./deploy_updates.sh
```

This script copies the systemd service files with Supabase credentials to the Pi.

## Testing Upload

After deployment, test the upload:

```bash
# Trigger a test capture
ssh pi@10.42.0.1 'sudo systemctl start ranch-camera.service'

# Check upload logs
ssh pi@10.42.0.1 'journalctl -u ranch-camera.service -n 20'
```

## Viewing Uploaded Images

Images are accessible via Supabase Storage dashboard:

1. Go to https://supabase.com/dashboard/project/dtzayqhebbrbvordmabh
2. Navigate to Storage → spypoint-images
3. Open folder: tophand-zero-04/YYYY/MM/DD/

Since the bucket is PUBLIC, images can also be accessed via direct URL:
```
https://dtzayqhebbrbvordmabh.supabase.co/storage/v1/object/public/spypoint-images/tophand-zero-04/2026/03/08/filename.jpg
```

## Image Upload Details

- **High Quality (HQ):** ~820KB saved to SD card (`/home/pi/camera/archive/`)
- **Compressed:** ~118KB uploaded to Supabase via cellular
- **Format:** JPEG, 2304x1296, quality=10 for cellular upload
- **Rotation:** 180° applied (camera mounted upside down)
