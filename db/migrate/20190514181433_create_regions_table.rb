class CreateRegionsTable < ActiveRecord::Migration[5.2]
  def change
    create_table "regions", force: :cascade do |t|
      t.datetime "created_at"
      t.integer "number"
      t.string "satellite_name"
      t.string "coverage"
      t.index ["number"], name: "index_region_on_number", unique: true
    end
  end  
end
