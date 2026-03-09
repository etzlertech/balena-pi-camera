-- Supabase Database Function to auto-delete tiny _S images
-- This function runs automatically whenever a file is uploaded to storage

-- Create a function that deletes tiny _S images
CREATE OR REPLACE FUNCTION delete_tiny_s_images()
RETURNS TRIGGER AS $$
BEGIN
  -- Check if the file is in the spypoint-images bucket
  IF NEW.bucket_id = 'spypoint-images' THEN
    -- Check if filename contains _S_ and file size is under 10 KB (10240 bytes)
    IF NEW.name LIKE '%\_S\_%' AND (NEW.metadata->>'size')::integer < 10240 THEN
      -- Log the deletion
      RAISE NOTICE 'Auto-deleting tiny _S image: % (% bytes)', NEW.name, (NEW.metadata->>'size');

      -- Delete the object
      DELETE FROM storage.objects WHERE id = NEW.id;

      -- Return NULL to prevent the insert
      RETURN NULL;
    END IF;
  END IF;

  -- Allow the insert for all other files
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create a trigger that fires BEFORE insert on storage.objects
DROP TRIGGER IF EXISTS auto_delete_tiny_s_images ON storage.objects;

CREATE TRIGGER auto_delete_tiny_s_images
  BEFORE INSERT ON storage.objects
  FOR EACH ROW
  EXECUTE FUNCTION delete_tiny_s_images();

-- Note: To enable this trigger, run the above SQL in your Supabase SQL Editor
-- The trigger will automatically prevent tiny _S images from being stored
