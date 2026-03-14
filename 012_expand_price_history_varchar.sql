-- 012_expand_price_history_varchar.sql
-- price_history VARCHAR(10) 컬럼 확장 (22001 에러 수정)
-- vrty_cd, unit_sz 등에 10자 초과 값이 들어오는 경우 처리

ALTER TABLE price_history
    ALTER COLUMN ctgry_cd  TYPE VARCHAR(20),
    ALTER COLUMN item_cd   TYPE VARCHAR(20),
    ALTER COLUMN vrty_cd   TYPE VARCHAR(20),
    ALTER COLUMN sigungu_cd TYPE VARCHAR(20),
    ALTER COLUMN unit      TYPE VARCHAR(20),
    ALTER COLUMN unit_sz   TYPE VARCHAR(20);
