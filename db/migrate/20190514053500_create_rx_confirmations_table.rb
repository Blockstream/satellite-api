class CreateRxConfirmationsTable < ActiveRecord::Migration[5.2]
  def change
    create_table "rx_confirmations", force: :cascade do |t|
      t.datetime "created_at"
      t.integer "order_id"
      t.integer "region_id"
      t.boolean "presumed", default: false
      t.index ["order_id"], name: "index_rx_confirmations_on_order_id"
    end
  end
end
