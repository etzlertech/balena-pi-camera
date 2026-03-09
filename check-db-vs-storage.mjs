// Check what's in database vs storage
import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = 'https://dtzayqhebbrbvordmabh.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR0emF5cWhlYmJyYnZvcmRtYWJoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg2ODA2NzIsImV4cCI6MjA4NDI1NjY3Mn0.hlDn444h_cxDf7BB3C3e68VrOfXtiljtsIwd0L1iF1w';
const BUCKET = 'spypoint-images';

const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

async function checkDbVsStorage() {
    // Get latest images from database
    console.log('📊 Checking database images table...\n');
    const { data: dbImages, error: dbError } = await supabase
        .from('images')
        .select('storage_path, captured_at, created_at')
        .order('created_at', { ascending: false })
        .limit(10);

    if (dbError) {
        console.error('❌ Database error:', dbError);
    } else {
        console.log(`Found ${dbImages.length} images in database (latest 10):`);
        dbImages.forEach((img, i) => {
            console.log(`  ${i + 1}. ${img.storage_path}`);
            console.log(`     Captured: ${img.captured_at}`);
            console.log(`     Created:  ${img.created_at}`);
        });
    }

    // Get latest files from storage (QN folder as example)
    console.log('\n📦 Checking storage bucket (QN folder)...\n');
    const { data: storageFiles, error: storageError } = await supabase.storage
        .from(BUCKET)
        .list('QN', {
            limit: 10,
            sortBy: { column: 'created_at', order: 'desc' }
        });

    if (storageError) {
        console.error('❌ Storage error:', storageError);
    } else {
        console.log(`Found ${storageFiles.length} files in storage (latest 10):`);
        storageFiles.forEach((file, i) => {
            if (file.id !== null) {
                console.log(`  ${i + 1}. ${file.name}`);
                console.log(`     Created: ${file.created_at}`);
                console.log(`     Size: ${(file.metadata?.size / 1024).toFixed(1)} KB`);
            }
        });
    }

    // Check for missing images
    console.log('\n🔍 Checking if storage files exist in database...\n');
    for (const file of storageFiles) {
        if (file.id !== null && !file.name.includes('thumb')) {
            const storagePath = `QN/${file.name}`;
            const { data: dbMatch } = await supabase
                .from('images')
                .select('storage_path, captured_at')
                .eq('storage_path', storagePath)
                .single();

            if (!dbMatch) {
                console.log(`❌ NOT in database: ${storagePath} (created ${file.created_at})`);
            }
        }
    }
}

checkDbVsStorage().catch(console.error);
