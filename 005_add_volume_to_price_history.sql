-- price_history 테이블에 volume_kg 컬럼 추가
ALTER TABLE price_history
    ADD COLUMN IF NOT EXISTS volume_kg NUMERIC DEFAULT NULL;
