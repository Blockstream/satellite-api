class CreateRegionsTable < ActiveRecord::Migration[5.2]
  def change
    create_table "regions", force: :cascade do |t|
      t.datetime "created_at"
      t.integer "number"
      t.string "satellite_name"
      t.string "coverage"
      t.index ["number"], name: "index_region_on_number", unique: true
    end
    
    execute "insert into regions (created_at, number, satellite_name, coverage) values ('2019-05-14 05:35:00.0', 0, 'Galaxy 18', 'North America')"
    execute "insert into regions (created_at, number, satellite_name, coverage) values ('2019-05-14 05:35:00.0', 1, 'Eutelsat 113', 'South America')"
    execute "insert into regions (created_at, number, satellite_name, coverage) values ('2019-05-14 05:35:00.0', 2, 'Telstar 11N', 'Africa')"
    execute "insert into regions (created_at, number, satellite_name, coverage) values ('2019-05-14 05:35:00.0', 3, 'Telstar 11N', 'Europe')"
    execute "insert into regions (created_at, number, satellite_name, coverage) values ('2019-05-14 05:35:00.0', 4, 'Telstar 18V', 'Asia')"
  end  
  
end
